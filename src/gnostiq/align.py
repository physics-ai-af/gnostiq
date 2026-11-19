"""Forecast/observation training tables."""

import logging

import numpy as np
import pandas as pd

from gnostiq import physics
from gnostiq.cfg import VARS
from gnostiq.ingest import precip, static

log = logging.getLogger("gnostiq")

GROSS = 15.0  # degC; past this the obs or the forecast is broken


def truth_rain(c):
    if c.truth.rain == "station":
        path = c.paths.interim / "station_rain.parquet"
        if not path.exists():
            raise FileNotFoundError(f"{path} missing; run `gnostiq build` after `gnostiq pull`")
        r = pd.read_parquet(path)[["day", "tp24"]]
    else:
        path = precip.cache(c)
        if not path.exists():
            raise FileNotFoundError(f"{path} missing; run `gnostiq pull --only precip`")
        r = pd.read_parquet(path)[["day", "tp24"]]
    v = VARS["tp24"]
    return r[r.tp24.between(v.lo, v.hi)].reset_index(drop=True)


def split(c, day):
    w = c.window
    d = pd.DatetimeIndex(day).normalize()
    lab = np.full(len(d), "other", dtype=object)
    lab[(d >= pd.Timestamp(c.nwp.start)) & (d <= pd.Timestamp(w.train_end))] = "train"
    lab[(d >= pd.Timestamp(w.test_start)) & (d <= pd.Timestamp(w.test_end))] = "test"
    return lab


def extras(c, models=None):
    out = {}
    for m in c.nwp.extra if models is None else models:
        path = c.paths.interim / f"nwp_{m}.parquet"
        if path.exists():
            out[m] = pd.read_parquet(path, columns=["valid", "lead_day", "f_t2m", "f_td2m"])
    return out


def features(c):
    path = c.paths.interim / f"nwp_{c.nwp.base}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"{path} missing; run `gnostiq pull`")
    h = physics.hourly_features(pd.read_parquet(path), c.site, static.z_model(c))
    return physics.add_extras(h, extras(c))


def build(c):
    h = features(c)
    obs = pd.read_parquet(c.paths.interim / "obs.parquet").rename(columns={"t": "o_t2m", "td": "o_td2m"})

    ph = h.merge(obs, on="valid", how="inner")
    gross = (ph.o_t2m - ph.t_prior).abs() > GROSS
    ph = ph[~gross].reset_index(drop=True)
    ph["split"] = split(c, ph.valid)
    c.paths.processed.mkdir(parents=True, exist_ok=True)
    ph.to_parquet(c.paths.processed / "pairs_hourly.parquet", index=False)

    d = physics.daily_features(h, c.truth.rain_h0)
    pdly = d.merge(truth_rain(c).rename(columns={"tp24": "o_tp24"}), on="day", how="inner")
    pdly["split"] = split(c, pdly.day)
    pdly.to_parquet(c.paths.processed / "pairs_daily.parquet", index=False)

    for name, p in (("hourly", ph), ("daily", pdly)):
        n = p.split.value_counts().to_dict()
        log.info(
            "pairs %s: %s%s", name, n, f", {int(gross.sum())} gross mismatches dropped" if name == "hourly" else ""
        )
        if not n.get("train") or not n.get("test"):
            raise ValueError(f"{name} pairs have no train or no test rows: {n}. Check windows against data coverage.")
    return ph, pdly
