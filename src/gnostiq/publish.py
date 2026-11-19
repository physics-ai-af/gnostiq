"""A public, tamper-evident record of each day's first forecast, on Autonomys Auto Drive."""

import gzip
import hashlib
import json
import logging
import os
import subprocess
from importlib import metadata

import pandas as pd
import requests

log = logging.getLogger("gnostiq")

ENDPOINT = "https://s3.auto-drive.autonomys.xyz"
GATEWAY = "https://gateway.autonomys.xyz/file/"
KEY = "AUTO_DRIVE_API_KEY"
BUCKET = "gnostiq"
SCHEMA = "gnostiq.record/1"
DAYS = 3  # how far back a missed day is still caught up


def sha256(b):
    return hashlib.sha256(b).hexdigest()


def pack(raw):
    # a fixed mtime makes the same forecast always the same bytes, so the same CID
    return gzip.compress(raw, compresslevel=9, mtime=0)


def unpack(b):
    # the gateway may or may not undo the gzip
    return gzip.decompress(b) if b[:2] == b"\x1f\x8b" else b


def commit(c):
    sha = os.environ.get("GNOSTIQ_COMMIT")
    if sha:
        return sha
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=c.source.parent, capture_output=True, text=True, check=True
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return out.stdout.strip() or None


def version():
    try:
        return metadata.version("gnostiq")
    except metadata.PackageNotFoundError:
        return None


def client():
    import boto3
    from botocore.config import Config

    # path-style, and no chunked checksums: Auto Drive answers those with 501
    cfg = Config(s3={"addressing_style": "path"}, request_checksum_calculation="when_required",
                 response_checksum_validation="when_required")  # fmt: skip
    return boto3.client("s3", endpoint_url=ENDPOINT, aws_access_key_id=os.environ[KEY],
                        aws_secret_access_key="unused", region_name="us-east-1", config=cfg)  # fmt: skip


def put(s3, key, body, kind):
    r = s3.put_object(Bucket=BUCKET, Key=key, Body=body, ContentType=kind)
    cid = r["ResponseMetadata"]["HTTPHeaders"].get("x-amz-meta-cid") or r.get("VersionId")
    if not cid:
        raise RuntimeError(f"Auto Drive returned no CID for {key}")
    return cid


def index_path(c):
    return c.paths.reports / "records.json"


def index(c):
    p = index_path(c)
    return json.loads(p.read_text()) if p.exists() else {"site": c.site.name, "records": []}


def firsts(c):
    # the first issue of each UTC day, the one the live check scores
    by_day = {}
    for p in sorted(c.paths.archive.glob("*.json.gz")):
        init = pd.to_datetime(p.name.split(".")[0], format="%Y%m%dT%H")
        by_day.setdefault(f"{init:%Y-%m-%d}", p)
    return by_day


def record(c, raw, fcid, size, previous):
    doc = json.loads(raw)
    models = c.paths.models
    return {
        "schema": SCHEMA,
        "site": {"name": c.site.name, "lat": c.site.lat, "lon": c.site.lon, "elev_m": c.site.elev},
        "issued_utc": doc["init_utc"],
        "published_utc": f"{pd.Timestamp.now('UTC'):%Y-%m-%dT%H:%M:%SZ}",
        "forecast": {
            "cid": fcid,
            "sha256": sha256(raw),
            "bytes": len(raw),
            "stored_bytes": size,
            "format": "forecast.json, gzip",
        },  # fmt: skip
        "model": {
            "trained_utc": doc["model_trained"],
            "trained_at": doc.get("trained_at", c.site.name),
            "hourly_sha256": sha256((models / "hourly.pt").read_bytes()),
            "daily_sha256": sha256((models / "daily.pt").read_bytes()) if (models / "daily.pt").exists() else None,
        },
        "code": {"version": version(), "commit": commit(c)},
        "config_sha256": sha256(c.source.read_bytes()),
        "sources": {
            "forecast": {"provider": "Open-Meteo", "base": c.nwp.base, "others": list(c.nwp.others)},
            "training": {
                "window": [str(c.window.start), str(c.window.train_end)],
                "temperature": c.truth.temp,
                "rain": c.truth.rain,
            },  # fmt: skip
        },
        "previous": previous,
    }


def run(c, days=DAYS, s3=None):
    idx = index(c)
    done = {r["day"] for r in idx["records"]}
    today = pd.Timestamp.now("UTC").tz_localize(None).floor("D")
    todo = {d: p for d, p in firsts(c).items() if d not in done and pd.Timestamp(d) > today - pd.Timedelta(days=days)}
    if not todo:
        log.info("publish %s: nothing new", c.site.name)
        return idx
    live = s3 is not None or bool(os.environ.get(KEY))
    out = c.paths.data / "published"
    out.mkdir(parents=True, exist_ok=True)
    if live and s3 is None:
        s3 = client()
    previous = idx["records"][-1]["record_cid"] if idx["records"] else None
    for day, path in sorted(todo.items()):
        gz = path.read_bytes()
        raw = unpack(gz)
        key = f"{c.site.name}/{day}"
        if not live:
            # nothing leaves the machine; Auto Drive is permanent, so test runs should not land there
            rec = record(c, raw, None, len(gz), previous)
            (out / f"{day}.dry-run.json").write_text(json.dumps(rec, indent=1))
            log.info("publish %s %s: dry run, set %s to upload", c.site.name, day, KEY)
            continue
        fcid = put(s3, f"{key}/forecast.json.gz", gz, "application/gzip")
        rec = record(c, raw, fcid, len(gz), previous)
        body = json.dumps(rec, indent=1).encode()
        rcid = put(s3, f"{key}/record.json", body, "application/json")
        (out / f"{day}.json.gz").write_bytes(gz)
        (out / f"{day}.record.json").write_bytes(body)
        idx["records"].append({"day": day, "issued_utc": rec["issued_utc"], "forecast_cid": fcid, "record_cid": rcid,
                               "sha256": rec["forecast"]["sha256"], "bytes": len(gz) + len(body)})  # fmt: skip
        idx["latest"], idx["bytes_total"] = rcid, sum(r["bytes"] for r in idx["records"])
        # written after each day, so a failure later on loses nothing already stored
        tmp = index_path(c).with_suffix(".part")
        tmp.write_text(json.dumps(idx, indent=1))
        tmp.replace(index_path(c))
        previous = rcid
        log.info("publish %s %s: record %s, forecast %s", c.site.name, day, rcid, fcid)
    return idx


def fetch(cid):
    r = requests.get(GATEWAY + cid, timeout=60)
    r.raise_for_status()
    return r.content


def verify(cid, depth=None, get=None):
    # walk back from a record; each forecast must hash to what its record says
    get = get or fetch
    out = []
    while cid and (depth is None or len(out) < depth):
        rec = json.loads(unpack(get(cid)))
        raw = unpack(get(rec["forecast"]["cid"]))
        doc = json.loads(raw)
        problems = []
        if sha256(raw) != rec["forecast"]["sha256"]:
            problems.append("forecast does not match its hash")
        if doc.get("init_utc") != rec["issued_utc"] or doc.get("site", {}).get("name") != rec["site"]["name"]:
            problems.append("forecast is for another issue or site")
        out.append({"record": cid, "site": rec["site"]["name"], "issued_utc": rec["issued_utc"],
                    "published_utc": rec.get("published_utc"), "ok": not problems, "problems": problems})  # fmt: skip
        cid = rec.get("previous")
    return out
