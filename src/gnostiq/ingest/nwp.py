"""Open-Meteo forecasts: archive by lead day, and the live run."""

import json
import logging
import time

import numpy as np
import pandas as pd
import requests

from gnostiq.io import UA, Missing, fetch

log = logging.getLogger("gnostiq")

PREV = "https://previous-runs-api.open-meteo.com/v1/forecast"
LIVE = "https://api.open-meteo.com/v1/forecast"

# one request per group, so a refused variable can't sink core
GROUPS = {
    "core": {
        "f_t2m": "temperature_2m",
        "f_td2m": "dew_point_2m",
        "f_tp": "precipitation",
        "f_msl": "pressure_msl",
        "f_sp": "surface_pressure",
        "f_cloud": "cloud_cover",
        "f_wspd": "wind_speed_10m",
        "f_wdir": "wind_direction_10m",
    },
    "column": {
        "f_cape": "cape",
        "f_tcwv": "total_column_integrated_water_vapour",
        "f_sw": "shortwave_radiation",
    },
    "levels": {
        "f_t850": "temperature_850hPa",
        "f_t700": "temperature_700hPa",
        "f_rh700": "relative_humidity_700hPa",
        "f_wspd850": "wind_speed_850hPa",
        "f_wdir850": "wind_direction_850hPa",
    },
}
CORE = ["f_t2m", "f_td2m", "f_tp", "f_msl"]
POINT = {k: GROUPS["core"][k] for k in ("f_t2m", "f_td2m", "f_tp")}


def models(c):
    return (c.nwp.base, *c.nwp.others)


def groups(c, model):
    # the networks read every base field and the core of each extra; compared models are only scored
    if model == c.nwp.base:
        return GROUPS
    return {"core": GROUPS["core"]} if model in c.nwp.extra else {"point": POINT}


def base_params(c, model):
    # elevation=nan turns off Open-Meteo's height downscaling
    return {
        "latitude": c.site.lat,
        "longitude": c.site.lon,
        "elevation": "nan",
        "models": model,
        "timezone": "GMT",
        "wind_speed_unit": "ms",
    }


def chunks(start, end, days):
    a = pd.Timestamp(start)
    end = pd.Timestamp(end)
    while a <= end:
        b = min(a + pd.Timedelta(days=days - 1), end)
        yield a.date(), b.date()
        a = b + pd.Timedelta(days=1)


def unreadable(c):
    bad = []
    for p in sorted((c.paths.raw / "nwp").glob("*/*.json")):
        try:
            json.loads(p.read_bytes())
        except ValueError:
            bad.append(p)
    return bad


def pull(c, refresh=False):
    for p in unreadable(c):
        log.warning("refetching unreadable %s/%s", p.parent.name, p.name)
        p.unlink()
    today = pd.Timestamp.now("UTC").tz_localize(None).floor("D")
    for model in models(c):
        for gname, gvars in groups(c, model).items():
            hourly = ",".join(f"{v}_previous_day{d}" for v in gvars.values() for d in c.lead_days)
            skip = c.paths.raw / "nwp" / model / f"{gname}.missing"
            if skip.exists() and not refresh:
                continue
            for a, b in chunks(c.nwp.start, today.date(), c.nwp.chunk_days):
                path = c.paths.raw / "nwp" / model / f"{gname}_{a}_{b}.json"
                # recent chunks are still filling in
                live = pd.Timestamp(b) >= today - pd.Timedelta(days=10)
                cached = path.exists()
                try:
                    fetch(
                        PREV,
                        path,
                        {**base_params(c, model), "hourly": hourly, "start_date": str(a), "end_date": str(b)},
                        max_age=6 * 3600 if live else None,
                        check=json.loads,
                    )
                except Missing as e:
                    if gname == "core" and model == c.nwp.base:
                        raise
                    log.warning("%s: variable group %r not served by the archive, skipped: %s", model, gname, e)
                    skip.parent.mkdir(parents=True, exist_ok=True)
                    skip.write_text(str(e))
                    break
                if not cached:
                    time.sleep(1)
        log.info("nwp %s cached", model)


def parse_prev(js, gvars, leads):
    h = js["hourly"]
    t = pd.to_datetime(h["time"])
    frames = []
    for d in leads:
        f = pd.DataFrame({"valid": t, "lead_day": d})
        for short, api in gvars.items():
            v = h.get(f"{api}_previous_day{d}")
            f[short] = np.asarray(v, dtype=float) if v is not None else np.nan
        frames.append(f)
    return pd.concat(frames, ignore_index=True)


def build(c):
    # older versions cached whatever came back; drop broken chunks so the next pull refetches them
    bad = unreadable(c)
    if bad:
        for p in bad:
            p.unlink()
        names = ", ".join(f"{p.parent.name}/{p.name}" for p in bad)
        raise RuntimeError(f"removed {len(bad)} unreadable forecast chunk(s): {names}; run `gnostiq pull --only nwp`")
    out = {}
    for model in models(c):
        d = c.paths.raw / "nwp" / model
        per_group = []
        for gname, gvars in groups(c, model).items():
            parts = [
                parse_prev(json.loads(p.read_text()), gvars, c.lead_days) for p in sorted(d.glob(f"{gname}_*.json"))
            ]
            if parts:
                g = pd.concat(parts, ignore_index=True).drop_duplicates(["valid", "lead_day"], keep="last")
                per_group.append(g.set_index(["valid", "lead_day"]))
        if not per_group:
            if model == c.nwp.base:
                raise FileNotFoundError(f"no NWP chunks in {d}; run `gnostiq pull --only nwp`")
            log.warning("nwp %s: nothing cached, skipped", model)
            continue
        df = pd.concat(per_group, axis=1).reset_index().sort_values(["lead_day", "valid"])
        df = df.dropna(subset=[k for k in CORE if k in df], how="all").reset_index(drop=True)
        c.paths.interim.mkdir(parents=True, exist_ok=True)
        df.to_parquet(c.paths.interim / f"nwp_{model}.parquet", index=False)
        empty = [k for k in df.columns if k.startswith("f_") and df[k].isna().all()]
        log.info("nwp %s: %d rows, %s..%s%s", model, len(df), df.valid.min(), df.valid.max(),
                 f", empty: {empty}" if empty else "")  # fmt: skip
        out[model] = df
    return out


def live(c, days=9):
    hourly = [v for g in GROUPS.values() for v in g.values()]
    names = {v: k for g in GROUPS.values() for k, v in g.items()}
    params = {**base_params(c, c.nwp.base), "forecast_days": days, "past_days": 2}
    try:
        js = _get(LIVE, {**params, "hourly": ",".join(hourly)})
    except Missing:
        js = _get(LIVE, {**params, "hourly": ",".join(GROUPS["core"].values())})
    h = js["hourly"]
    df = pd.DataFrame({"valid": pd.to_datetime(h["time"])})
    for api, short in names.items():
        v = h.get(api)
        df[short] = np.asarray(v, dtype=float) if v is not None else np.nan
    return df.dropna(subset=["f_t2m"]).reset_index(drop=True), js.get("elevation")


def live_extra(c, days=9):
    out = {}
    for m in c.nwp.others:
        params = {**base_params(c, m), "forecast_days": days, "past_days": 2, "hourly": "temperature_2m,dew_point_2m"}
        try:
            h = _get(LIVE, params)["hourly"]
        except (Missing, requests.RequestException) as e:
            # its inputs fall back to "missing", which the net saw in training
            log.warning("live %s unavailable: %s", m, e)
            h = {"time": [], "temperature_2m": [], "dew_point_2m": []}
        out[m] = pd.DataFrame(
            {
                "valid": pd.to_datetime(h["time"]),
                "f_t2m": np.asarray(h["temperature_2m"], dtype=float),
                "f_td2m": np.asarray(h["dew_point_2m"], dtype=float),
            }
        )
    return out


def _get(url, params, tries=3):
    err = None
    for i in range(tries):
        try:
            r = requests.get(url, params=params, headers=UA, timeout=120)
        except requests.RequestException as e:
            err = e
        else:
            if r.status_code in (400, 404):
                raise Missing(f"{r.status_code}: {r.text[:300]}")
            if r.ok:
                return r.json()
            err = requests.HTTPError(f"{r.status_code}: {r.text[:200]}")
        time.sleep(20 * 2**i)
    raise err
