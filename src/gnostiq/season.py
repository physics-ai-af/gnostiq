"""A scored season: what each system would have issued from the forecast archive, against NiMet reports."""

import json
import logging

import numpy as np
import pandas as pd

from gnostiq import align, baselines, dist, live, model, physics, verify
from gnostiq.ingest import nimet, nwp

log = logging.getLogger("gnostiq")

CORE = ["gnostiq", "raw", "lapse", "emos", "emos_multi", "clim"]
REFS = ["raw", "lapse", "emos", "emos_multi", "clim"]


def window(c, start=None, end=None, today=None):
    today = pd.Timestamp(today or pd.Timestamp.now("UTC").tz_localize(None)).floor("D")
    if start:
        return pd.Timestamp(start), pd.Timestamp(end or today - pd.Timedelta(days=1))
    # the latest wet season with at least a month in it
    for year in (today.year, today.year - 1):
        a = pd.Timestamp(year, min(c.window.wet), 1)
        b = min(pd.Timestamp(year, max(c.window.wet), 1) + pd.offsets.MonthEnd(), today - pd.Timedelta(days=1))
        if b - a >= pd.Timedelta(days=30):
            return a, b
    raise ValueError("no wet season to score yet")


def issued(c, start, end):
    nwp.build(c)
    h = align.features(c)
    h = h[(h.valid >= start) & (h.valid < end + pd.Timedelta(days=1)) & h.t_prior.notna() & h.dep_prior.notna()]
    h = h.reset_index(drop=True)
    if h.empty:
        raise ValueError(f"no archived forecasts from {start.date()} to {end.date()}; run `gnostiq pull --only nwp`")
    rows = []

    def emit(system, var, mu, sigma=np.nan):
        rows.append(h[["valid", "lead_day"]].assign(var=var, system=system, mu=np.asarray(mu, float), sigma=sigma))

    t_mu, t_sig, td_mu, td_sig = model.predict_hourly(model.load(c.paths.models / "hourly.pt"), h)
    emit("gnostiq", "t2m", t_mu, t_sig)
    emit("gnostiq", "td2m", td_mu, td_sig)

    pairs = c.paths.trained / "pairs_hourly.parquet"
    fit = pd.read_parquet(pairs).query("split == 'train'") if pairs.exists() else None
    obs = c.paths.interim / "obs.parquet"
    obs = pd.read_parquet(obs).rename(columns={"t": "o_t2m", "td": "o_td2m"}) if obs.exists() else None
    others = align.extras(c, c.nwp.others)
    for var, (ocol, fcol, prior) in baselines.HVARS.items():
        emit("raw", var, h[fcol])
        emit("lapse", var, h[prior])
        for m, e in others.items():
            emit(f"raw:{m}", var, h[["valid", "lead_day"]].merge(e, on=["valid", "lead_day"], how="left")[fcol])
        if fit is not None:
            # fitted where the networks were trained, applied to this site's own prior
            f = fit[fit[ocol].notna()]
            emit("emos", var, *baselines.emos(c, f, h, prior, ocol))
            extra = physics.extra_deltas(f, var)
            if extra:
                emit("emos_multi", var, *baselines.emos(c, f, h, prior, ocol, extra, name="emos_multi"))
        if obs is not None:
            emit("clim", var, *baselines.clim_hourly(c, obs, ocol, h.valid))
    return pd.concat(rows, ignore_index=True).dropna(subset=["mu"])


def track(c, pred, rep):
    # day by day, the forecast each day would have had a day ahead, beside what NiMet reported
    p = pred[(pred.lead_day == 1) & pred.system.isin(["gnostiq", "raw"])]
    w = p.pivot_table(index=["valid", "var"], columns="system", values="mu")
    sig = p[p.system == "gnostiq"].set_index(["valid", "var"]).sigma
    w = w.assign(q10=w.gnostiq - dist.Z80 * sig, q90=w.gnostiq + dist.Z80 * sig)
    w = w.join(rep.set_index(["valid", "var"]).obs, how="left").reset_index()
    rows = live.by_day(w, c.site.tz)
    return {"tz": c.site.tz, "windows": live.WINDOWS, "rows": rows, "summary": live.tally(rows)}


def stats(g):
    return {"n": len(g), "mae": round(float(g.err.mean()), 3), "crps": round(float(g.crps.mean()), 3)}


def run(c, start=None, end=None):
    start, end = window(c, start, end)
    if start <= pd.Timestamp(c.window.train_end):
        raise ValueError(f"season starts {start.date()}, inside the training window (to {c.window.train_end})")
    pred = issued(c, start, end)
    o, where = nimet.obs(c, start, end + pd.Timedelta(hours=23))
    rep = live.long(o, "nimet")
    j = live.score(pred.merge(rep, on=["valid", "var"]))
    out_vars, j = live.summarize(j, ["valid", "lead_day"], CORE, [*REFS, *live.others(j)], np.random.default_rng(0))
    for var, v in out_vars.items():
        g = j[j["var"] == var]
        v["by_lead"] = {s: {int(k): stats(x) for k, x in gs.groupby("lead_day")} for s, gs in g.groupby("system")}
        v["by_month"] = {
            s: {int(k): stats(x) for k, x in gs.groupby(gs.valid.dt.month)} for s, gs in g.groupby("system")
        }
    used = j[(j.system == "gnostiq") & (j["var"] == "t2m")].valid.drop_duplicates()
    site = {"lat": c.site.lat, "lon": c.site.lon}
    out = {
        "site": c.site.name,
        "trained_at": c.donor or c.site.name,
        "base": c.nwp.base,
        "window": [f"{start:%Y-%m-%d}", f"{end:%Y-%m-%d}"],
        "train_end": str(c.window.train_end),
        "truth": "nimet",
        "station": {"wigos": nimet.wigos(c), **where, "km": round(nimet.km(site, where), 1) if where else None},
        "reports": int(rep.valid.nunique()),
        # a daytime-only station leaves the night unscored
        "hours": {int(k): int(n) for k, n in used.dt.hour.value_counts().sort_index().items()},
        "vars": out_vars,
        "track": track(c, pred, rep),
    }
    c.paths.reports.mkdir(parents=True, exist_ok=True)
    (c.paths.reports / "season.json").write_text(json.dumps(out, indent=1))
    (c.paths.reports / "season.md").write_text(markdown(out))
    log.info("season %s to %s: %d reports, %d temperature cases", *out["window"], out["reports"],
             out["vars"]["t2m"]["cases"])  # fmt: skip
    return out


def markdown(doc):
    st = doc["station"]
    where = f"{st['lat']:.3f} N {st['lon']:.3f} E, {st['km']} km from the site" if st.get("lat") is not None else ""
    out = [
        f"# Season: {doc['site']}, {doc['window'][0]} to {doc['window'][1]}",
        "",
        f"What each system would have issued from the archived forecasts, scored against NiMet synops from "
        f"{st['wigos']} ({where}). Networks trained at {doc['trained_at']} up to {doc['train_end']}; nothing here "
        "was seen in training.",
        "",
        f"{doc['reports']} reports. Hours scored (UTC): "
        + ", ".join(f"{h:02d} ({n})" for h, n in doc["hours"].items()),
        "",
        "Skill is 1 - CRPS/reference with 95% intervals from resampling whole days. Raw models are single values, "
        "so their CRPS is their absolute error.",
        "",
    ]
    for var, v in doc["vars"].items():
        out += [f"## {var} ({v['cases']} cases)", "", "| system | n | bias | MAE | CRPS |", "|---|---|---|---|---|"]
        for s, r in sorted(v["systems"].items()):
            out.append(f"| {s} | {r['n']} | {r['bias']:+.2f} | {r['mae']:.2f} | {r['crps']:.2f} |")
        out.append("")
        for ref, sk in v["skill"].items():
            out.append(f"CRPSS vs {ref}: {verify.skill_cell(sk)}")
        leads = sorted({k for x in v["by_lead"].values() for k in x})
        if leads:
            names = sorted(v["by_lead"])
            out += ["", "CRPS by lead day:", "", "| system | " + " | ".join(f"day {k}" for k in leads) + " |",
                    "|---|" + "---|" * len(leads)]  # fmt: skip
            for s in names:
                cells = [f"{v['by_lead'][s][k]['crps']:.2f}" if k in v["by_lead"][s] else "-" for k in leads]
                out.append(f"| {s} | " + " | ".join(cells) + " |")
        out.append("")
    out += live.track_md(doc.get("track"), "forecast a day ahead, rebuilt from the archive")
    return "\n".join(out)
