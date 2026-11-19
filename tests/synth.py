"""Synthetic raw files in the real on-disk formats. Scores from this data mean nothing."""

import json

import numpy as np
import pandas as pd

from gnostiq.ingest import nwp, precip

Z_MODEL = 1000.0
# null in the live archive for ecmwf_ifs025
NULL_IN_ARCHIVE = {"f_cape", "f_tcwv"}


# column order of a real GHCNh .psv (NII0000DNJO, Nov 2026)
GHCNH_VARS = [
    "temperature", "dew_point_temperature", "station_level_pressure", "sea_level_pressure", "wind_direction",
    "wind_speed", "wind_gust", "precipitation", "relative_humidity", "wet_bulb_temperature",
    *[f"pres_wx_{k}{i}" for k in ("MW", "AU", "AW") for i in (1, 2, 3)],
    "snow_depth", "visibility", "altimeter", "pressure_3hr_change", "sky_condition", "sky_condition_baseht",
    "ceiling_height",
    *[f"sky_cover_{k}_{i}" for k in ("layer", "layer_baseht", "summation", "summation_baseht") for i in (1, 2, 3, 4)],
    *[f"precipitation_{k}" for k in ("5_minute", "15_minute", "3_hour", "6_hour", "9_hour", "12_hour", "15_hour",
                                     "18_hour", "21_hour", "24_hour")],
    "REM",
]  # fmt: skip
GHCNH_HEAD = [
    "STATION", "Station_name", "DATE", "Year", "Month", "Day", "Hour", "Minute", "LATITUDE", "LONGITUDE", "ELEVATION",
    *[v + s for v in GHCNH_VARS for s in ("", "_Measurement_Code", "_Quality_Code", "_Report_Type", "_Source_Code",
                                           "_Source_Station_ID")],
]  # fmt: skip


def ghcnh_psv(path, rows, drop=()):
    head = [k for k in GHCNH_HEAD if k not in drop]
    pd.DataFrame(rows).reindex(columns=head).to_csv(path, sep="|", index=False, na_rep="")


def ar1(rng, n, phi, sd):
    e = rng.normal(0, sd * np.sqrt(1 - phi**2), n)
    x = np.empty(n)
    x[0] = e[0]
    for i in range(1, n):
        x[i] = phi * x[i - 1] + e[i]
    return x


def truth(c, end, seed=0):
    rng = np.random.default_rng(seed)
    t = pd.date_range(pd.Timestamp(c.window.start), pd.Timestamp(end) + pd.Timedelta(hours=23), freq="h")
    n = len(t)
    doy, hl = t.day_of_year.to_numpy(), (t.hour.to_numpy() + 1) % 24
    dry = 0.5 * (1 + np.cos(2 * np.pi * (doy - 15) / 365))
    diur = np.cos(2 * np.pi * (hl - 15) / 24)
    temp = 22 + 3 * np.cos(2 * np.pi * (doy - 100) / 365) + (3 + 3 * dry) * diur + ar1(rng, n, 0.97, 1.2)
    dep = np.maximum(0.3, 2 + 13 * dry + 2.5 * diur + ar1(rng, n, 0.95, 1.0))

    days = pd.date_range(t[0].floor("D"), t[-1].floor("D"), freq="D")
    dd = 0.5 * (1 + np.cos(2 * np.pi * (days.day_of_year.to_numpy() - 15) / 365))
    wet = rng.random(len(days)) < 0.8 * (1 - dd) ** 1.5
    amt = np.where(wet, 1 + rng.gamma(0.9, 11, len(days)), 0.0)
    return pd.DataFrame({"valid": t, "t": temp, "td": temp - dep, "dry": dry}), pd.DataFrame({"day": days, "tp24": amt})


def hourly_rain(valid, daily):
    amt = daily.set_index("day").tp24.reindex(valid.dt.floor("D")).to_numpy()
    return np.where(valid.dt.hour.isin([15, 16, 17]).to_numpy(), amt / 3, 0.0)


def write_station(c, tru, rng, day_only=False):
    d = c.paths.raw / "station"
    d.mkdir(parents=True, exist_ok=True)
    s = c.site
    line = f"{'NIM00065134':<11} {s.lat:8.4f} {s.lon:9.4f} {s.elev:6.1f} {'':2} {'JOS':<30} {'':3} {'':3} {s.wmo:<5}"
    (d / "ghcnh-station-list.txt").write_text(line + "\n")

    s = tru[tru.valid.dt.hour % 3 == 0].reset_index(drop=True)
    if day_only:
        s = s[s.valid.dt.hour.between(6, 18)].reset_index(drop=True)
    s = s[rng.random(len(s)) > 0.06].reset_index(drop=True)
    n = len(s)
    t = (s.t + rng.normal(0, 0.3, n)).round(1)
    v = s.valid.dt
    psv = pd.DataFrame(
        {
            "STATION": "NIM00065134", "Station_name": "JOS", "DATE": v.strftime("%Y-%m-%dT%H:%M:%S"),
            "Year": v.year, "Month": v.strftime("%m"), "Day": v.strftime("%d"), "Hour": v.strftime("%H"),
            "Minute": "00", "LATITUDE": c.site.lat, "LONGITUDE": c.site.lon, "ELEVATION": c.site.elev,
            "temperature": t, "temperature_Measurement_Code": "", "temperature_Quality_Code": "5",
            "temperature_Report_Type": "FM12",
            "dew_point_temperature": np.minimum(t, (s.td + rng.normal(0, 0.4, n)).round(1)),
            "dew_point_temperature_Quality_Code": "5",
            "station_level_pressure": (871.5 + rng.normal(0, 1.5, n)).round(1),
            "station_level_pressure_Quality_Code": "5",
            "wind_speed": np.abs(rng.normal(3, 1.5, n)).round(1), "wind_speed_Quality_Code": "5",
        }
    )  # fmt: skip
    psv.loc[5, "temperature"] = 61.0  # one gross error for QC to catch
    ghcnh_psv(d / "GHCNh_NIM00065134_por.psv", psv)

    m = tru[tru.valid.dt.hour.between(7, 17)]
    for y, g in m.groupby(m.valid.dt.year):
        out = pd.DataFrame(
            {
                "station": c.site.icao, "valid": g.valid.dt.strftime("%Y-%m-%d %H:%M"),
                "lon": c.site.lon, "lat": c.site.lat,
                "elevation": c.site.elev, "tmpf": (np.round(g.t) * 1.8 + 32).round(2),
                "dwpf": (np.round(g.td) * 1.8 + 32).round(2), "alti": 30.03, "mslp": "M", "sknt": 6.0,
            }
        )  # fmt: skip
        out.to_csv(d / f"iem_{c.site.icao}_{y}.csv", index=False)
    # ingest wants a file per year through the current one
    for y in range(int(m.valid.dt.year.max()) + 1, pd.Timestamp.now("UTC").year + 1):
        (d / f"iem_{c.site.icao}_{y}.csv").write_text("station,valid,lon,lat,elevation,tmpf,dwpf,alti,mslp,sknt\n")


def model_fields(tru, daily, lead, rng, bias=2.0):
    # warm-biased, noisier with lead
    n = len(tru)
    hl = (tru.valid.dt.hour.to_numpy() + 1) % 24
    t = tru.t.to_numpy() + bias + 1.0 * np.cos(2 * np.pi * (hl - 15) / 24) + ar1(rng, n, 0.9, 0.7 + 0.25 * lead)
    td = np.minimum(t, tru.td.to_numpy() + 0.8 + ar1(rng, n, 0.9, 0.8 + 0.3 * lead))
    f = daily.copy()
    hit = rng.random(len(f)) > 0.08 * lead
    f["tp24"] = np.where(hit, f.tp24 * rng.lognormal(-0.1, 0.35 + 0.08 * lead, len(f)), 0) + rng.gamma(
        0.3, 1.5, len(f)
    ) * (1 - tru.dry.iloc[::24].to_numpy()[: len(f)])
    msl = 1012 + ar1(rng, n, 0.99, 2.0)
    wet = 1 - tru.dry.to_numpy()
    return {
        "f_t2m": t, "f_td2m": td, "f_tp": hourly_rain(tru.valid, f), "f_msl": msl,
        "f_sp": msl * np.exp(-Z_MODEL / (29.2717 * (t + 273.15 + 3.25))),
        "f_cloud": np.clip(20 + 60 * wet + rng.normal(0, 15, n), 0, 100), "f_wspd": np.abs(rng.normal(3, 1.5, n)),
        "f_wdir": np.where(wet > 0.5, 225, 45) + rng.normal(0, 25, n) % 360,
        "f_cape": np.clip(1500 * wet + rng.normal(0, 300, n), 0, None), "f_tcwv": 18 + 30 * wet + rng.normal(0, 3, n),
        "f_sw": np.clip(900 * np.cos(2 * np.pi * (hl - 12) / 24), 0, None), "f_t850": t - 3.5, "f_t700": t - 12.5,
        "f_rh700": np.clip(30 + 50 * wet + rng.normal(0, 10, n), 1, 100), "f_wspd850": np.abs(rng.normal(8, 3, n)),
        "f_wdir850": np.full(n, 90.0),
    }  # fmt: skip


def write_nwp(c, tru, daily, rng, bare=False):
    tru = tru[tru.valid >= pd.Timestamp(c.nwp.start)].reset_index(drop=True)
    daily = daily[daily.day >= pd.Timestamp(c.nwp.start)].reset_index(drop=True)
    for model in nwp.models(c):
        groups = nwp.groups(c, model)
        fields = {d: model_fields(tru, daily, d, rng, bias=2.0 if model == c.nwp.base else 3.0) for d in c.lead_days}
        day = tru.valid.dt.floor("D")
        for a, b in nwp.chunks(c.nwp.start, tru.valid.iloc[-1].date(), c.nwp.chunk_days):
            sel = ((day >= pd.Timestamp(a)) & (day <= pd.Timestamp(b))).to_numpy()
            for gname, gvars in groups.items():
                if bare and gname == "levels":
                    continue
                hourly = {"time": tru.valid[sel].dt.strftime("%Y-%m-%dT%H:%M").tolist()}
                for short, api in gvars.items():
                    for d in c.lead_days:
                        vals = [round(float(v), 2) for v in fields[d][short][sel]]
                        hourly[f"{api}_previous_day{d}"] = (
                            [None] * len(vals) if bare and short in NULL_IN_ARCHIVE else vals
                        )
                path = c.paths.raw / "nwp" / model / f"{gname}_{a}_{b}.json"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(
                    json.dumps(
                        {"latitude": c.site.lat, "longitude": c.site.lon, "elevation": Z_MODEL, "hourly": hourly}
                    )
                )


def write_chirps(c, daily, rng):
    out = daily.copy()
    out["tp24"] = (out.tp24 * rng.lognormal(0, 0.15, len(out))).round(2)
    out["pt"] = out.tp24
    out["stage"] = "final"
    path = precip.cache(c)
    path.parent.mkdir(parents=True, exist_ok=True)
    out[["day", "pt", "tp24", "stage"]].to_parquet(path, index=False)


def live_frame(c, init, seed=1):
    rng = np.random.default_rng(seed)
    t = pd.date_range(init.floor("D") - pd.Timedelta(days=2), periods=11 * 24, freq="h")
    doy, hl = t.day_of_year.to_numpy(), (t.hour.to_numpy() + 1) % 24
    dry = 0.5 * (1 + np.cos(2 * np.pi * (doy - 15) / 365))
    temp = 22 + 3 * np.cos(2 * np.pi * (doy - 100) / 365) + (3 + 3 * dry) * np.cos(2 * np.pi * (hl - 15) / 24)
    tru = pd.DataFrame({"valid": t, "t": temp, "td": temp - (2 + 13 * dry), "dry": dry})
    daily = pd.DataFrame({"day": pd.date_range(t[0], periods=11, freq="D"), "tp24": rng.gamma(0.9, 8, 11)})
    return pd.DataFrame({"valid": t, **model_fields(tru, daily, 1, rng)})


def make(c, end, seed=0, bare=False):
    rng = np.random.default_rng(seed + 100)
    tru, daily = truth(c, end, seed)
    c.paths.ensure()
    write_station(c, tru, rng)
    write_nwp(c, tru, daily, rng, bare)
    write_chirps(c, daily, rng)
    static = {"z_station": c.site.elev, "z_model_hyps": Z_MODEL, "z_model_api": None, "base": c.nwp.base}
    (c.paths.processed / "static.json").write_text(json.dumps(static))
