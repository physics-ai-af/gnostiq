"""Station temperature and dewpoint checks."""

import logging

import numpy as np
import pandas as pd

from gnostiq.cfg import VARS

log = logging.getLogger("gnostiq")

STEP = 8.0  # degC, vs both neighbours
FLAT_N, FLAT_H = 12, 24  # readings, hours
CLIM_MIN = 8.0  # degC


def spikes(x):
    s = x.dropna()
    t = s.index.to_series()
    near = (t.diff() <= pd.Timedelta(hours=3)) & (t.diff(-1).abs() <= pd.Timedelta(hours=3))
    a, b = s - s.shift(1), s - s.shift(-1)
    bad = near.to_numpy() & (a.abs() > STEP) & (b.abs() > STEP) & (np.sign(a) == np.sign(b))
    return s.index[bad]


def flatlines(x):
    s = x.dropna()
    if s.empty:
        return s.index
    run = (s != s.shift()).cumsum()
    t = s.index.to_series()
    n = s.groupby(run).transform("size")
    span = t.groupby(run).transform("max") - t.groupby(run).transform("min")
    return s.index[((n >= FLAT_N) & (span >= pd.Timedelta(hours=FLAT_H))).to_numpy()]


def outliers(x):
    s = x.dropna()
    key = [s.index.month, s.index.hour]
    med = s.groupby(key).transform("median")
    mad = (s - med).abs().groupby(key).transform("median")
    n = s.groupby(key).transform("size")
    return s.index[((n >= 10) & ((s - med).abs() > np.maximum(CLIM_MIN, 6 * 1.4826 * mad))).to_numpy()]


def run(c):
    o = pd.read_parquet(c.paths.interim / "station.parquet").set_index("valid").sort_index()
    n0 = {k: int(o[k].notna().sum()) for k in ("t", "td")}
    counts = {}

    for k in ("t", "td"):
        v = VARS[k]
        bad = o[k].notna() & ~o[k].between(v.lo, v.hi)
        counts[f"{k} range"] = int(bad.sum())
        o.loc[bad, k] = np.nan

    # a small overshoot is rounding
    over = o.td - o.t
    counts["td above t by > 0.5"] = int((over > 0.5).sum())
    o.loc[over > 0.5, "td"] = np.nan
    o["td"] = o.td.where(~(over > 0) | o.td.isna(), o.t)

    for k in ("t", "td"):
        for name, fn in (("spike", spikes), ("flatline", flatlines), ("climatological outlier", outliers)):
            idx = fn(o[k])
            counts[f"{k} {name}"] = len(idx)
            o.loc[idx, k] = np.nan

    # td can't be checked without t
    o.loc[o.t.isna(), "td"] = np.nan
    out = o.loc[o.t.notna(), ["t", "td", "src"]].reset_index()
    out.to_parquet(c.paths.interim / "obs.parquet", index=False)

    lines = [
        "# Station QC",
        "",
        f"Source mix: {out.src.value_counts().to_dict()}",
        "",
        "| check | removed |",
        "|---|---|",
    ]
    lines += [f"| {k} | {v} |" for k, v in counts.items()]
    lines += ["", f"t: {n0['t']} reported, {int(out.t.notna().sum())} kept",
              f"td: {n0['td']} reported, {int(out.td.notna().sum())} kept", ""]  # fmt: skip
    c.paths.reports.mkdir(parents=True, exist_ok=True)
    (c.paths.reports / "qc.md").write_text("\n".join(lines))
    log.info("qc: kept %d of %d temperatures", out.t.notna().sum(), n0["t"])
    return out
