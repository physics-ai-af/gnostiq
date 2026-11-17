"""Station observations from GHCNh and IEM."""

import logging
import time

import numpy as np
import pandas as pd

from gnostiq.io import Missing, fetch

log = logging.getLogger("gnostiq")

GHCNH = "https://www.ncei.noaa.gov/oa/global-historical-climatology-network/hourly"
IEM = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"

# ISD codes that passed NOAA's checks
GOOD_QC = {"", "0", "1", "4", "5", "9"}
COLS = {
    "t": "temperature",
    "td": "dew_point_temperature",
    "ps": "station_level_pressure",
    "slp": "sea_level_pressure",
    "qnh": "altimeter",
    "wspd": "wind_speed",
    "p6": "precipitation_6_hour",
    "p12": "precipitation_12_hour",
    "p24": "precipitation_24_hour",
}
RAIN = ("p6", "p12", "p24")
OBS = ["t", "td", "ps", "slp", "qnh", "wspd", *RAIN]
DAY = 86400


def num(df, col):
    if col not in df:
        return pd.Series(np.nan, index=df.index)
    return pd.to_numeric(df[col], errors="coerce")


def text(df, col):
    if col not in df:
        return pd.Series("", index=df.index)
    return df[col].fillna("").astype(str).str.strip()


def slotted(o):
    # half-hourly METARs would land on the wrong hour
    m = o.ts.dt.minute
    o = o[(m <= 10) | (m >= 50)].copy()
    o["slot"] = o.ts.dt.round("h")
    return o.drop(columns="ts").groupby("slot").first()


def candidates(c, refresh=False):
    path = fetch(
        f"{GHCNH}/doc/ghcnh-station-list.txt",
        c.paths.raw / "station" / "ghcnh-station-list.txt",
        max_age=30 * DAY if refresh else None,
    )
    # only the first four columns are relied on
    lat0, lat1, lon0, lon1 = c.site.bbox
    rows = []
    for line in path.read_text(errors="replace").splitlines():
        p = line.replace(",", " ").split()
        try:
            lat, lon, elev = float(p[1]), float(p[2]), float(p[3])
        except (IndexError, ValueError):
            continue
        wmo = c.site.wmo in p[4:]
        if wmo or (lat0 <= lat <= lat1 and lon0 <= lon <= lon1):
            rows.append({"id": p[0], "lat": lat, "lon": lon, "elev": elev, "rest": " ".join(p[4:]), "wmo": wmo})
    return pd.DataFrame(rows, columns=["id", "lat", "lon", "elev", "rest", "wmo"])


def resolve_id(c):
    if c.site.ghcnh:
        return c.site.ghcnh
    cand = candidates(c)
    hit = cand[cand.wmo]
    if len(hit) == 1:
        return hit.id.iloc[0]
    if len(cand) == 1:
        return cand.id.iloc[0]
    raise Missing(f"{len(cand)} GHCNh candidates for WMO {c.site.wmo}; run scripts/gate.py and set site.ghcnh")


def ghcnh_path(c, sid, refresh=False):
    return fetch(
        f"{GHCNH}/access/by-station/GHCNh_{sid}_por.psv",
        c.paths.raw / "station" / f"GHCNh_{sid}_por.psv",
        max_age=DAY if refresh else None,
    )


def read_ghcnh(path, start):
    keep = {"DATE", "Year", "Month", "Day", "Hour", "Minute", "Latitude", "Longitude", "Elevation"}
    stems = tuple(COLS.values())
    df = pd.read_csv(path, sep="|", dtype=str, usecols=lambda k: k in keep or k.startswith(stems), low_memory=False)
    if "DATE" in df:
        ts = pd.to_datetime(df["DATE"], utc=True)
    else:
        parts = df[["Year", "Month", "Day", "Hour", "Minute"]].astype(int)
        parts.columns = ["year", "month", "day", "hour", "minute"]
        ts = pd.to_datetime(parts, utc=True)
    df["ts"] = ts.dt.tz_localize(None)
    return df[df.ts >= pd.Timestamp(start)].reset_index(drop=True)


def tidy_ghcnh(df):
    o = pd.DataFrame({"ts": df.ts})
    for k, col in COLS.items():
        v = num(df, col)
        if k in RAIN:
            v = v.mask(v.isna() & text(df, f"{col}_Measurement_Code").str.contains("T"), 0.0)
        o[k] = v.where(text(df, f"{col}_Quality_Code").isin(GOOD_QC))
    o["rtype"] = text(df, "temperature_Report_Type")
    return slotted(o)


def iem_paths(c, refresh=False):
    out = []
    now = pd.Timestamp.now("UTC").year
    for y in range(c.window.start.year, now + 1):
        path = c.paths.raw / "station" / f"iem_{c.site.icao}_{y}.csv"
        age = DAY if (refresh and y == now) else None
        if not path.exists() or (age and time.time() - path.stat().st_mtime > age):
            params = {
                "station": c.site.icao,
                "data": ["tmpf", "dwpf", "alti", "mslp", "sknt"],
                "sts": f"{y}-01-01T00:00Z",
                "ets": f"{y + 1}-01-01T00:00Z",
                "tz": "Etc/UTC",
                "format": "onlycomma",
                "latlon": "yes",
                "elev": "yes",
                "missing": "M",
                "report_type": [3, 4],
            }
            fetch(IEM, path, params, max_age=age)
            time.sleep(2)  # IEM rate-limits per IP
        out.append(path)
    return out


def read_iem(paths):
    df = pd.concat([pd.read_csv(p, dtype=str) for p in paths], ignore_index=True)
    df["ts"] = pd.to_datetime(df["valid"], utc=True).dt.tz_localize(None)
    o = pd.DataFrame(
        {
            "ts": df.ts,
            "t": (num(df, "tmpf") - 32) / 1.8,
            "td": (num(df, "dwpf") - 32) / 1.8,
            "qnh": num(df, "alti") * 33.8639,
            "slp": num(df, "mslp"),
            "wspd": num(df, "sknt") * 0.514444,
        }
    )
    meta = df[[k for k in ("lat", "lon", "elevation") if k in df]].drop_duplicates()
    return slotted(o), meta


def rain_days(o, start, end):
    # rain day runs 06-06 UTC, labelled by its start
    days = pd.date_range(start, end, freq="D")
    hour = pd.Timedelta(hours=1)

    def at(col, off):
        if col not in o:
            return np.full(len(days), np.nan)
        return o[col].reindex(days + off * hour).to_numpy(dtype=float)

    a = at("p24", 30)
    b = at("p12", 18) + at("p12", 30)
    k = at("p6", 12) + at("p6", 18) + at("p6", 24) + at("p6", 30)
    tot = np.where(np.isnan(a), np.where(np.isnan(b), k, b), a)
    return pd.Series(tot, index=days, name="tp24")


def pull(c, refresh=False):
    try:
        sid = resolve_id(c)
        ghcnh_path(c, sid, refresh)
        log.info("GHCNh %s cached", sid)
    except Missing as e:
        log.warning("GHCNh unavailable: %s", e)
    try:
        iem_paths(c, refresh)
        log.info("IEM %s cached", c.site.icao)
    except Missing as e:
        log.warning("IEM unavailable: %s", e)


def build(c):
    raw = c.paths.raw / "station"
    start = c.window.start
    g = i = None

    psv = sorted(raw.glob("GHCNh_*_por.psv"))
    if c.site.ghcnh:
        psv = [p for p in psv if c.site.ghcnh in p.name]
    if psv and c.truth.temp != "iem":
        if len(psv) > 1:
            raise ValueError(f"several GHCNh files in {raw}; set site.ghcnh")
        g = tidy_ghcnh(read_ghcnh(psv[0], start))
    csvs = sorted(raw.glob(f"iem_{c.site.icao}_*.csv"))
    if csvs and c.truth.temp != "ghcnh":
        i, _ = read_iem(csvs)

    if g is None and i is None:
        raise FileNotFoundError(f"no station files for truth.temp={c.truth.temp!r} in {raw}; run `gnostiq pull`")
    if g is None:
        o = i.assign(src="iem")
    elif i is None:
        o = g.assign(src="ghcnh")
    else:
        o = g.combine_first(i)
        o["src"] = np.where(g.t.reindex(o.index).notna(), "ghcnh", "iem")
    for k in OBS:
        if k not in o:
            o[k] = np.nan
    o = o[[*OBS, "src"]].sort_index()
    o.index.name = "valid"

    c.paths.interim.mkdir(parents=True, exist_ok=True)
    o.reset_index().to_parquet(c.paths.interim / "station.parquet", index=False)
    end = pd.Timestamp.now("UTC").tz_localize(None).floor("D")
    rain = rain_days(o, start, end).dropna().rename_axis("day").reset_index()
    rain.to_parquet(c.paths.interim / "station_rain.parquet", index=False)
    log.info("station: %d slots (%s), %d rain days", len(o), o.src.value_counts().to_dict(), len(rain))
    return o
