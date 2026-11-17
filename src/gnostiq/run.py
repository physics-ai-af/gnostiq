"""Live forecast."""

import json
import logging

import numpy as np
import pandas as pd

from gnostiq import dist, model, physics
from gnostiq.ingest import nwp, static

log = logging.getLogger("gnostiq")


def lead_days(valid, init):
    # archived day-N leads are >= 24N h, so round up
    return np.maximum(np.ceil(np.asarray((valid - init) / pd.Timedelta(hours=24))).astype(int), 1)


def forecast(c, frame, init):
    hb = model.load(c.paths.models / "hourly.pt")
    db = model.load(c.paths.models / "daily.pt")
    top = max(c.lead_days)

    # blank inputs the nets never saw in training
    frame = frame.assign(lead_day=0, **{k: np.nan for k in physics.NWP_COLS if k not in hb["cols"]})
    h = physics.hourly_features(frame, c.site, static.z_model(c))
    h["lead_day"] = lead_days(h.valid, init)
    fut = h[(h.valid > init) & (h.lead_day <= top) & h.t_prior.notna() & h.dep_prior.notna()].reset_index(drop=True)
    t_mu, t_sig, td_mu, td_sig = model.predict_hourly(hb, fut)

    def band(mu, sig, cap=None):
        lo, hi = mu - dist.Z80 * sig, mu + dist.Z80 * sig
        if cap is not None:
            mu, lo, hi = np.minimum(mu, cap[1]), np.minimum(lo, cap[0]), np.minimum(hi, cap[2])
        return np.round(lo, 1), np.round(mu, 1), np.round(hi, 1)

    t = band(t_mu, t_sig)
    # td <= t, quantile by quantile
    td = band(td_mu, td_sig, cap=t)
    hourly = [
        {"valid_utc": v.strftime("%Y-%m-%dT%H:%MZ"), "lead_day": int(ld),
         "t2m": {"q10": float(t[0][i]), "q50": float(t[1][i]), "q90": float(t[2][i])},
         "td2m": {"q10": float(td[0][i]), "q50": float(td[1][i]), "q90": float(td[2][i])},
         "raw": {"t2m": round(float(fut.f_t2m[i]), 1), "td2m": round(float(fut.f_td2m[i]), 1)}}
        for i, (v, ld) in enumerate(zip(fut.valid, fut.lead_day, strict=True))
    ]  # fmt: skip

    h0 = c.truth.rain_h0
    d = physics.daily_features(h, h0, keys=())
    start = d.day + pd.Timedelta(hours=h0)
    d["lead_day"] = lead_days(start + pd.Timedelta(hours=24), init)
    # skip days with under 3 h left
    d = d[(start + pd.Timedelta(hours=21) > init) & (d.lead_day <= top)].reset_index(drop=True)
    daily = []
    if len(d):
        p, m, k = model.predict_daily(db, d)
        q = dist.hurdle_quantiles(p, m, k, c.wet_mm)
        p10 = dist.hurdle_exceed(p, m, k, c.wet_mm, c.heavy_mm)
        for i, row in d.iterrows():
            daily.append({
                "date": str(row.day.date()),
                "start_utc": (row.day + pd.Timedelta(hours=h0)).strftime("%Y-%m-%dT%H:%MZ"),
                "lead_day": int(row.lead_day), "p_wet": round(float(p[i]), 3), "p_heavy": round(float(p10[i]), 3),
                "tp24": {"q50": round(float(q[i, 49]), 1), "q90": round(float(q[i, 89]), 1)},
                "raw_tp24": round(float(row.f_tp24), 1),
            })  # fmt: skip

    return {
        "site": {"name": c.site.name, "lat": c.site.lat, "lon": c.site.lon, "elev_m": c.site.elev, "tz": c.site.tz},
        "init_utc": init.strftime("%Y-%m-%dT%H:%MZ"),
        "base_model": c.nwp.base,
        "model_trained": hb["trained"],
        "thresholds": {"wet_mm": c.wet_mm, "heavy_mm": c.heavy_mm},
        "hourly": hourly,
        "daily": daily,
    }


def run(c):
    frame, _ = nwp.live(c)
    init = pd.Timestamp.now("UTC").tz_localize(None).floor("h")
    doc = forecast(c, frame, init)
    c.paths.reports.mkdir(parents=True, exist_ok=True)
    path = c.paths.reports / "forecast.json"
    tmp = path.with_name(path.name + ".part")
    tmp.write_text(json.dumps(doc))
    tmp.replace(path)
    log.info("forecast: %d hourly steps, %d days, init %s", len(doc["hourly"]), len(doc["daily"]), doc["init_utc"])
    return doc
