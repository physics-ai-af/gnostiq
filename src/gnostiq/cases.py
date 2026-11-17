"""Replays of the wettest test days."""

import json
import logging

import pandas as pd

log = logging.getLogger("gnostiq")

N_CASES = 3
SYSTEMS = ["gnostiq", "emos", "raw"]


def run(c):
    base = pd.read_parquet(c.paths.processed / "pred_daily_base.parquet")
    mod = pd.read_parquet(c.paths.processed / "pred_daily_model.parquet")
    pred = pd.concat([base, mod], ignore_index=True)
    pred = pred[(pred.split == "test") & pred.system.isin(SYSTEMS)]

    # need every lead for a full replay
    g = pred[pred.system == "gnostiq"].groupby("day").agg(n=("lead_day", "nunique"), obs=("obs", "first"))
    top = g[g.n == len(c.lead_days)].obs.nlargest(N_CASES)

    cases = []
    for day, obs in top.items():
        rows = pred[pred.day == day].sort_values("lead_day", ascending=False)
        series = {}
        for s, x in rows.groupby("system"):
            series[s] = [
                {"lead_day": int(r.lead_day), "p_heavy": round(float(r.p10), 3), "p_wet": round(float(r.p1), 3),
                 "q50": round(float(r.q50), 1), "q90": round(float(r.q90), 1)}
                for r in x.itertuples()
            ]  # fmt: skip
        cases.append({"date": str(day.date()), "obs_mm": round(float(obs), 1), "systems": series})

    out = {"heavy_mm": c.heavy_mm, "wet_mm": c.wet_mm, "cases": cases}
    c.paths.reports.mkdir(parents=True, exist_ok=True)
    (c.paths.reports / "cases.json").write_text(json.dumps(out, indent=1))
    log.info("cases: %s", [(k["date"], k["obs_mm"]) for k in cases])
    return out
