"""Test-window scorecard."""

import json
import logging

import numpy as np
import pandas as pd

from gnostiq import dist

log = logging.getLogger("gnostiq")

CORE_H = ["clim", "persist", "raw", "lapse", "emos", "emos_multi", "gnostiq"]
CORE_D = ["clim", "persist", "raw", "emos", "gnostiq"]
REFS = ["clim", "raw", "emos", "emos_multi"]
BOOT = 1000
EDGES = np.linspace(0, 1, 11)


def common(pred, keys, core):
    have = [s for s in core if s in set(pred.system)]
    n = pred[pred.system.isin(have)].groupby(keys).system.nunique()
    ok = n[n == len(have)].index
    return pred.set_index(keys).loc[lambda d: d.index.isin(ok)].reset_index(), have


def boot_skill(day, a, b, rng):
    # resample whole days; errors within a day are dependent
    g = pd.DataFrame({"a": a, "b": b}).groupby(np.asarray(day)).sum()
    sa, sb = g.a.to_numpy(), g.b.to_numpy()
    if sb.sum() <= 0 or len(sa) < 5:
        return None
    idx = rng.integers(0, len(sa), (BOOT, len(sa)))
    bs = 1 - sa[idx].sum(1) / np.maximum(sb[idx].sum(1), 1e-12)
    lo, hi = np.quantile(bs, [0.025, 0.975])
    return {"skill": float(1 - sa.sum() / sb.sum()), "lo": float(lo), "hi": float(hi), "days": int(len(sa))}


def r(x):
    return None if x is None or not np.isfinite(x) else round(float(x), 4)


def hourly_scores(g):
    err = g.mu - g.obs
    prob = g.sigma > 0
    cov = (np.abs(err[prob]) <= dist.Z80 * g.sigma[prob]).mean() if prob.any() else np.nan
    return {
        "n": int(len(g)),
        "bias": r(err.mean()),
        "mae": r(err.abs().mean()),
        "crps": r(g.crps.mean()),
        "cov80": r(cov),
    }


def load(c, name):
    base = c.paths.processed / f"pred_{name}_base.parquet"
    if not base.exists():
        raise FileNotFoundError(f"{base} missing; run `gnostiq baselines`")
    parts = [pd.read_parquet(base)]
    mod = c.paths.processed / f"pred_{name}_model.parquet"
    if mod.exists():
        parts.append(pd.read_parquet(mod))
    pred = pd.concat(parts, ignore_index=True)
    return pred[pred.split == "test"]


def hourly(c, rng):
    pred = load(c, "hourly")
    out = {}
    for var, pv in pred.groupby("var"):
        pv, have = common(pv, ["valid", "lead_day"], CORE_H)
        pv["crps"] = dist.crps_norm(pv.obs, pv.mu, pv.sigma.fillna(0))
        pv["day"] = pv.valid.dt.floor("D")
        systems = {}
        for s, g in pv.groupby("system"):
            systems[s] = {
                "overall": hourly_scores(g),
                "by_lead": {int(k): hourly_scores(x) for k, x in g.groupby("lead_day")},
                "by_month": {int(k): hourly_scores(x) for k, x in g.groupby(g.valid.dt.month)},
            }
        skill = {}
        if "gnostiq" in have:
            wide = pv[pv.system.isin(have)].pivot(index=["valid", "lead_day"], columns="system", values="crps")
            day = wide.index.get_level_values("valid").floor("D")
            lead = wide.index.get_level_values("lead_day")
            for ref in [x for x in REFS if x in have]:
                skill[ref] = {
                    "overall": boot_skill(day, wide.gnostiq, wide[ref], rng),
                    "by_lead": {int(k): boot_skill(day[lead == k], wide.gnostiq[lead == k], wide[ref][lead == k], rng)
                                for k in sorted(set(lead))},
                }  # fmt: skip
        out[var] = {"n_cases": int(pv.groupby(["valid", "lead_day"]).ngroups), "systems": systems, "crpss": skill}
    return out


def ets(fc, ob):
    hits, fa, miss = (fc & ob).sum(), (fc & ~ob).sum(), (~fc & ob).sum()
    rand = (hits + fa) * (hits + miss) / max(len(ob), 1)
    den = hits + fa + miss - rand
    return float((hits - rand) / den) if den > 0 else np.nan


def daily_scores(g, c):
    o1, o10 = g.obs >= c.wet_mm, g.obs >= c.heavy_mm
    return {
        "n": int(len(g)),
        "brier1": r(((g.p1 - o1) ** 2).mean()),
        "brier10": r(((g.p10 - o10) ** 2).mean()),
        "crps": r(g.crps.mean()),
        "ets1": r(ets((g.p1 >= 0.5).to_numpy(), o1.to_numpy())),
        "ets10": r(ets((g.p10 >= 0.5).to_numpy(), o10.to_numpy())),
    }


def reliability(p, o):
    b = np.clip(np.digitize(p, EDGES) - 1, 0, 9)
    rows = []
    for i in range(10):
        m = b == i
        if m.any():
            rows.append({"bin": i, "p": r(p[m].mean()), "freq": r(o[m].mean()), "n": int(m.sum())})
    return rows


def daily(c, rng):
    pred = load(c, "daily")
    pred, have = common(pred, ["day", "lead_day"], CORE_D)
    pred["crps"] = dist.crps_quantiles(pred.obs.to_numpy(), pred[dist.QCOLS].to_numpy(float))
    o1, o10 = pred.obs >= c.wet_mm, pred.obs >= c.heavy_mm
    pred["b1"], pred["b10"] = (pred.p1 - o1) ** 2, (pred.p10 - o10) ** 2

    systems = {}
    for s, g in pred.groupby("system"):
        systems[s] = {
            "overall": daily_scores(g, c),
            "by_lead": {int(k): daily_scores(x, c) for k, x in g.groupby("lead_day")},
            "by_month": {int(k): daily_scores(x, c) for k, x in g.groupby(g.day.dt.month)},
        }

    skill, rel = {}, {}
    if "gnostiq" in have:
        core = pred[pred.system.isin(have)]
        for metric, name in (("crps", "crpss"), ("b1", "bss1"), ("b10", "bss10")):
            wide = core.pivot(index=["day", "lead_day"], columns="system", values=metric)
            day = wide.index.get_level_values("day")
            lead = wide.index.get_level_values("lead_day")
            skill[name] = {}
            for ref in [x for x in REFS if x in have]:
                skill[name][ref] = {
                    "overall": boot_skill(day, wide.gnostiq, wide[ref], rng),
                    "by_lead": {int(k): boot_skill(day[lead == k], wide.gnostiq[lead == k], wide[ref][lead == k], rng)
                                for k in sorted(set(lead))},
                }  # fmt: skip
        for s in [x for x in ("gnostiq", "emos") if x in have]:
            g = pred[pred.system == s]
            rel[s] = {
                "p1": reliability(g.p1.to_numpy(), (g.obs >= c.wet_mm).to_numpy()),
                "p10": reliability(g.p10.to_numpy(), (g.obs >= c.heavy_mm).to_numpy()),
            }
    n = pred.groupby(["day", "lead_day"]).ngroups
    base_rate = {"wet": r(o1[pred.system == have[0]].mean()), "heavy": r(o10[pred.system == have[0]].mean())}
    return {"n_cases": int(n), "base_rate": base_rate, "systems": systems, "skill": skill, "reliability": rel}


def fmt(x, nd=2):
    return "-" if x is None else f"{x:.{nd}f}"


def skill_cell(s):
    return "-" if not s else f"{s['skill']:+.3f} [{s['lo']:+.3f}, {s['hi']:+.3f}]"


def markdown(card):
    m = card["meta"]
    out = [f"# Scorecard: {m['site']}", "",
           f"Test window {m['test'][0]} to {m['test'][1]}. Base model {m['base']}. "
           f"Temperature truth: {m['truth']['temp']}. Rain truth: {m['truth']['rain']}.", "",
           "Skill is 1 - score/reference; brackets are 95% intervals from resampling whole days. "
           "An interval that includes zero is not evidence of skill. Systems showing a smaller n lack some cases "
           "(for example a model without 7-day data) and are not directly comparable.", ""]  # fmt: skip
    for var, v in card["hourly"].items():
        out += [
            f"## {var} ({v['n_cases']} cases)",
            "",
            "| system | n | bias | MAE | CRPS | 80% coverage |",
            "|---|---|---|---|---|---|",
        ]
        for s, d in v["systems"].items():
            o = d["overall"]
            out.append(
                f"| {s} | {o['n']} | {fmt(o['bias'])} | {fmt(o['mae'])} | {fmt(o['crps'])} | {fmt(o['cov80'])} |"
            )
        for ref, sk in v["crpss"].items():
            out += ["", f"CRPSS vs {ref}: {skill_cell(sk['overall'])}", "", "| lead day | CRPSS |", "|---|---|"]
            out += [f"| {k} | {skill_cell(x)} |" for k, x in sk["by_lead"].items()]
        out.append("")
    d = card["daily"]
    out += [f"## tp24 ({d['n_cases']} cases; wet-day rate {fmt(d['base_rate']['wet'])}, "
            f"heavy-day rate {fmt(d['base_rate']['heavy'])})", "",
            "| system | n | Brier wet | Brier heavy | CRPS | ETS wet | ETS heavy |",
            "|---|---|---|---|---|---|---|"]  # fmt: skip
    for s, x in d["systems"].items():
        o = x["overall"]
        out.append(f"| {s} | {o['n']} | {fmt(o['brier1'], 3)} | {fmt(o['brier10'], 3)} | {fmt(o['crps'])} | "
                   f"{fmt(o['ets1'])} | {fmt(o['ets10'])} |")  # fmt: skip
    for name, refs in d["skill"].items():
        for ref, sk in refs.items():
            out += ["", f"{name} vs {ref}: {skill_cell(sk['overall'])}"]
    return "\n".join(out) + "\n"


def run(c):
    rng = np.random.default_rng(0)
    card = {
        "meta": {
            "site": c.site.name,
            "base": c.nwp.base,
            "test": [str(c.window.test_start), str(c.window.test_end)],
            "train": [str(c.nwp.start), str(c.window.train_end)],
            "truth": {
                "temp": c.truth.temp,
                "rain": c.truth.rain if c.truth.rain == "station" else f"chirps-{c.truth.chirps_flavor}",
            },
            "thresholds": {"wet_mm": c.wet_mm, "heavy_mm": c.heavy_mm},
            "generated": pd.Timestamp.now("UTC").strftime("%Y-%m-%dT%H:%MZ"),
        },
        "hourly": hourly(c, rng),
        "daily": daily(c, rng),
    }
    c.paths.reports.mkdir(parents=True, exist_ok=True)
    (c.paths.reports / "scorecard.json").write_text(json.dumps(card, indent=1))
    (c.paths.reports / "scorecard.md").write_text(markdown(card))
    log.info("scorecard written to %s", c.paths.reports / "scorecard.md")
    return card
