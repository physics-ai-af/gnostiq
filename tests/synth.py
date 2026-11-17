"""Synthetic raw files in the real on-disk formats. Scores from this data mean nothing."""

import numpy as np
import pandas as pd


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
    psv = pd.DataFrame(
        {
            "Station_ID": "NIM00065134", "Station_name": "JOS", "DATE": s.valid.dt.strftime("%Y-%m-%dT%H:%M:%S"),
            "Latitude": c.site.lat, "Longitude": c.site.lon, "Elevation": c.site.elev,
            "temperature": t, "temperature_Measurement_Code": "", "temperature_Quality_Code": "5",
            "temperature_Report_Type": "FM-12",
            "dew_point_temperature": np.minimum(t, (s.td + rng.normal(0, 0.4, n)).round(1)),
            "dew_point_temperature_Quality_Code": "5",
            "station_level_pressure": (871.5 + rng.normal(0, 1.5, n)).round(1),
            "station_level_pressure_Quality_Code": "5",
            "wind_speed": np.abs(rng.normal(3, 1.5, n)).round(1), "wind_speed_Quality_Code": "5",
        }
    )  # fmt: skip
    psv.loc[5, "temperature"] = 61.0  # one gross error for QC to catch
    psv.to_csv(d / "GHCNh_NIM00065134_por.psv", sep="|", index=False, na_rep="")

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
