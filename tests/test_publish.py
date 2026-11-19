import gzip
import json
import shutil

import pandas as pd
import pytest
import synth

from gnostiq import cli, publish, run

DAY = pd.Timedelta(days=1)
HOUR = pd.Timedelta(hours=1)


class Store:
    # stands in for Auto Drive: content-addressed and permanent
    def __init__(self):
        self.blobs, self.keys = {}, []

    def put_object(self, Bucket, Key, Body, ContentType):
        assert Bucket == publish.BUCKET
        cid = "bafk" + publish.sha256(Body)[:40]
        self.blobs[cid] = Body
        self.keys.append(Key)
        return {"ResponseMetadata": {"HTTPHeaders": {"x-amz-meta-cid": cid}}, "VersionId": cid}

    def get(self, cid):
        return self.blobs[cid]


def issue(c, init):
    doc = run.forecast(c, synth.live_frame(c, init), init)
    (c.paths.archive / f"{init:%Y%m%dT%H}.json.gz").write_bytes(publish.pack(json.dumps(doc).encode()))
    return doc


@pytest.fixture
def site(trained, monkeypatch):
    c = trained
    for p in (c.paths.archive, c.paths.data / "published"):
        shutil.rmtree(p, ignore_errors=True)
    publish.index_path(c).unlink(missing_ok=True)
    c.paths.archive.mkdir(parents=True)
    monkeypatch.delenv(publish.KEY, raising=False)
    today = pd.Timestamp.now("UTC").tz_localize(None).floor("D")
    # an old day past the catch-up window, then two days with the later run of each not the one stored
    issue(c, today - 10 * DAY + 2 * HOUR)
    docs = [issue(c, today - d * DAY + h * HOUR) for d in (2, 1) for h in (2, 5)]
    yield c, docs[0::2]
    shutil.rmtree(c.paths.archive, ignore_errors=True)
    publish.index_path(c).unlink(missing_ok=True)


def test_each_days_first_forecast_is_stored_with_a_chained_record(site):
    c, firsts = site
    store = Store()
    idx = publish.run(c, s3=store)
    days = [d["init_utc"][:10] for d in firsts]
    assert [r["day"] for r in idx["records"]] == days
    assert store.keys == [f"{c.site.name}/{d}/{k}" for d in days for k in ("forecast.json.gz", "record.json")]
    recs = [json.loads(store.get(r["record_cid"])) for r in idx["records"]]
    assert recs[0]["previous"] is None and recs[1]["previous"] == idx["records"][0]["record_cid"]
    for rec, doc in zip(recs, firsts, strict=True):
        assert rec["schema"] == publish.SCHEMA and rec["issued_utc"] == doc["init_utc"]
        assert json.loads(gzip.decompress(store.get(rec["forecast"]["cid"]))) == doc
        assert rec["model"]["hourly_sha256"] == publish.sha256((c.paths.models / "hourly.pt").read_bytes())
        assert rec["config_sha256"] == publish.sha256(c.source.read_bytes())
        assert rec["sources"]["forecast"]["base"] == c.nwp.base
    assert idx["latest"] == idx["records"][-1]["record_cid"]
    assert idx["bytes_total"] == sum(len(b) for b in store.blobs.values())
    # nothing new, nothing sent; Auto Drive keeps everything, so a repeat upload would only cost space
    publish.run(c, s3=store)
    assert len(store.keys) == 4


def test_the_same_forecast_always_packs_to_the_same_bytes():
    raw = json.dumps({"init_utc": "2026-11-19T07:00Z"}).encode()
    assert publish.pack(raw) == publish.pack(raw) and publish.unpack(publish.pack(raw)) == raw


def test_anyone_can_walk_the_chain_and_a_changed_forecast_is_caught(site):
    c, _ = site
    store = Store()
    latest = publish.run(c, s3=store)["latest"]
    rows = publish.verify(latest, get=store.get)
    assert [r["ok"] for r in rows] == [True, True] and rows[0]["issued_utc"] > rows[1]["issued_utc"]
    # a gateway that undoes the gzip changes nothing
    assert all(r["ok"] for r in publish.verify(latest, get=lambda cid: publish.unpack(store.get(cid))))
    assert len(publish.verify(latest, depth=1, get=store.get)) == 1

    old = json.loads(store.get(rows[1]["record"]))
    doc = json.loads(gzip.decompress(store.get(old["forecast"]["cid"])))
    doc["hourly"][0]["t2m"]["q50"] += 1.0
    store.blobs[old["forecast"]["cid"]] = publish.pack(json.dumps(doc).encode())
    rows = publish.verify(latest, get=store.get)
    assert [r["ok"] for r in rows] == [True, False] and "hash" in rows[1]["problems"][0]


def test_without_a_key_nothing_leaves_the_machine(site, monkeypatch):
    c, _ = site
    monkeypatch.setattr(publish, "client", lambda: pytest.fail("no client without a key"))
    publish.run(c)
    assert not publish.index_path(c).exists()
    assert len(list((c.paths.data / "published").glob("*.dry-run.json"))) == 2


def test_verify_record_needs_no_config_and_fails_loudly(site, monkeypatch, capsys, tmp_path):
    c, _ = site
    store = Store()
    latest = publish.run(c, s3=store)["latest"]
    monkeypatch.setattr(publish, "fetch", store.get)
    monkeypatch.setenv("GNOSTIQ_CFG", str(tmp_path / "missing.toml"))
    cli.main(["verify-record", latest])
    assert "2 records checked, 0 failed" in capsys.readouterr().out
    store.blobs[latest] = json.dumps({**json.loads(store.get(latest)), "issued_utc": "2020-01-01T00:00Z"}).encode()
    with pytest.raises(SystemExit):
        cli.main(["verify-record", latest])
    assert "FAILED" in capsys.readouterr().out
