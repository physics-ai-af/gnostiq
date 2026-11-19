"""NiMet SYNOP reports from its WIS2 node, decoded to GeoJSON by the node's OGC API."""

import json
import logging
import math
import time

import numpy as np
import pandas as pd

from gnostiq.io import fetch

log = logging.getLogger("gnostiq")

ITEMS = "https://wis2.nimet.gov.ng/oapi/collections/urn:wmo:md:ng-nimet:surface-based-observations.synop/items"
LIMIT = 500  # the node's default page; it warns against larger ones
HOUR = 3600
NAMES = {
    "air_temperature": "t",
    "dewpoint_temperature": "td",
    "non_coordinate_pressure": "ps",
    "pressure_reduced_to_mean_sea_level": "slp",
    "wind_speed": "wspd",
}
COLS = list(NAMES.values())


def wigos(c):
    return f"0-20000-0-{c.site.wmo}"


def months(start, end):
    a = pd.Timestamp(start).to_period("M")
    for p in pd.period_range(a, pd.Timestamp(end).to_period("M"), freq="M"):
        yield p.start_time, p.end_time.floor("s")


def pull(c, start=None, end=None, refresh=False):
    today = pd.Timestamp.now("UTC").tz_localize(None)
    start = pd.Timestamp(start or c.nwp.start)
    end = pd.Timestamp(end or today)
    paths = []
    for a, b in months(start, end):
        # the current month still fills in; past months don't change
        fresh = refresh or b >= today - pd.Timedelta(days=3)
        off = 0
        while True:
            path = c.paths.raw / "nimet" / f"{c.site.wmo}_{a:%Y%m}_{off:05d}.json"
            span = f"{a:%Y-%m-%dT%H:%M:%SZ}/{b:%Y-%m-%dT%H:%M:%SZ}"
            params = {
                "wigos_station_identifier": wigos(c),
                "datetime": span,
                "limit": LIMIT,
                "offset": off,
                "f": "json",
            }
            cached = path.exists()
            # an unreachable node should fail in minutes, not hours
            fetch(ITEMS, path, params, max_age=HOUR if fresh else None, tries=2, timeout=60, check=json.loads)
            js = json.loads(path.read_text())
            paths.append(path)
            n = len(js["features"])
            off += n
            if not cached:
                time.sleep(1)
            if n == 0 or off >= js.get("numberMatched", off):
                break
    log.info("nimet %s: %d pages from %s to %s", wigos(c), len(paths), start.date(), end.date())
    return paths


def to_utc(s):
    return pd.to_datetime(s, utc=True).dt.tz_localize(None)


def read(paths):
    rows, where = [], {}
    for p in paths:
        for f in json.loads(p.read_text())["features"]:
            q = f["properties"]
            if q["name"] in NAMES and q["value"] is not None:
                rows.append((q["id"], q["reportTime"], NAMES[q["name"]], float(q["value"]), q["units"]))
            xyz = (f.get("geometry") or {}).get("coordinates") or []
            if len(xyz) == 3:
                where = {"lon": xyz[0], "lat": xyz[1], "elev": xyz[2]}
    df = pd.DataFrame(rows, columns=["id", "time", "var", "value", "units"]).drop_duplicates("id")
    if df.empty:
        return pd.DataFrame(columns=COLS, index=pd.DatetimeIndex([], name="valid")), where
    df.loc[df.units == "K", "value"] -= 273.15
    df.loc[df.units == "Pa", "value"] /= 100.0
    df["time"] = to_utc(df.time)
    # synop reports are on the hour; anything else would land on the wrong one
    m = df.time.dt.minute
    df = df[(m <= 10) | (m >= 50)].assign(valid=lambda d: d.time.dt.round("h"))
    o = df.pivot_table(index="valid", columns="var", values="value", aggfunc="first")
    return o.reindex(columns=COLS).sort_index(), where


def obs(c, start, end, refresh=False):
    o, where = read(pull(c, start, end, refresh))
    o = o[(o.index >= pd.Timestamp(start)) & (o.index <= pd.Timestamp(end))]
    # the same gross limits the other sources go through
    ok_t = o.t.between(-10, 50)
    o = o.assign(t=o.t.where(ok_t), td=o.td.where(ok_t & o.td.between(-40, 40) & (o.td <= o.t + 0.5)))
    return o, where


def km(a, b):
    if not a or not b:
        return np.nan
    la, lb = math.radians(a["lat"]), math.radians(b["lat"])
    d = (
        math.sin((lb - la) / 2) ** 2
        + math.cos(la) * math.cos(lb) * math.sin(math.radians(b["lon"] - a["lon"]) / 2) ** 2
    )
    return 2 * 6371.0 * math.asin(math.sqrt(d))
