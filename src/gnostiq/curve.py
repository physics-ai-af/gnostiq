"""Learning curve: skill against the length of the forecast archive."""

import json
import logging

import numpy as np
import pandas as pd

from gnostiq import baselines, dist, model, physics, train, verify

log = logging.getLogger("gnostiq")

MONTHS = [1, 2, 3, 6]
REFS = ["emos", "emos_multi", "clim"]


def weeks(valid):
    return np.asarray((pd.DatetimeIndex(valid).normalize() - pd.Timestamp("2000-01-03")).days // 7)


def sizes(n_weeks):
    out = [(f"{m} mo", round(m * 52 / 12)) for m in MONTHS if round(m * 52 / 12) < n_weeks]
    return out + [("all", n_weeks)]


def run(c):
    p = train.hourly_pairs(c)
    obs = pd.read_parquet(c.paths.interim / "obs.parquet").rename(columns={"t": "o_t2m", "td": "o_td2m"})
    pool = p[p.split == "train"].reset_index(drop=True)
    te = p[p.split == "test"].reset_index(drop=True)
    wk = weeks(pool.valid)
    # nested random weeks: every size spans the seasons, and each contains the smaller ones
    order = np.random.default_rng(0).permutation(np.unique(wk))
    clim = {var: baselines.clim_hourly(c, obs, ocol, te.valid) for var, (ocol, _, _) in baselines.HVARS.items()}
    rng = np.random.default_rng(1)

    rows = []
    for label, n in sizes(len(order)):
        keep = order[:n]
        sub = pool[np.isin(wk, keep)]
        hold = np.isin(weeks(sub.valid), keep[::5])
        log.info("curve %s: %d weeks, %d pairs", label, n, len(sub))
        b = train.fit_hourly(c, sub, hold, quiet=True)
        t_mu, t_sig, td_mu, td_sig = model.predict_hourly(b, te)
        mine = {"t2m": (t_mu, t_sig), "td2m": (td_mu, td_sig)}
        for var, (ocol, _, prior) in baselines.HVARS.items():
            sys = {"clim": clim[var], "emos": baselines.emos(c, sub, te, prior, ocol), "gnostiq": mine[var]}
            extra = physics.extra_deltas(te, var)
            if extra:
                sys["emos_multi"] = baselines.emos(c, sub, te, prior, ocol, extra, name="emos_multi")
            y = te[ocol].to_numpy(float)
            ok = np.isfinite(y)
            for mu, sg in sys.values():
                ok &= np.isfinite(mu) & np.isfinite(sg)
            crps = {s: dist.crps_norm(y[ok], mu[ok], sg[ok]) for s, (mu, sg) in sys.items()}
            day = te.valid[ok].dt.floor("D").to_numpy()
            rows.append(
                {
                    "var": var,
                    "size": label,
                    "weeks": int(n),
                    "pairs": int(len(sub)),
                    "cases": int(ok.sum()),
                    "crps": {s: float(v.mean()) for s, v in crps.items()},
                    "skill": {r: verify.boot_skill(day, crps["gnostiq"], crps[r], rng) for r in REFS if r in crps},
                    "inflate": b["inflate"],
                }
            )

    doc = {
        "site": c.site.name,
        "pool": [str(pool.valid.min().date()), str(pool.valid.max().date())],
        "test": [str(c.window.test_start), str(c.window.test_end)],
        "rows": rows,
    }
    c.paths.reports.mkdir(parents=True, exist_ok=True)
    (c.paths.reports / "curve.json").write_text(json.dumps(doc, indent=1))
    (c.paths.reports / "curve.md").write_text(markdown(doc))
    log.info("learning curve written to %s", c.paths.reports / "curve.md")
    return doc


def markdown(doc):
    out = [
        f"# Learning curve: {doc['site']}",
        "",
        f"Training pairs are whole weeks drawn at random from {doc['pool'][0]} to {doc['pool'][1]}, so every size "
        "spans the seasons, and each size contains the smaller ones. EMOS and gnostiq are refit at every size; "
        "climatology always uses the full station record, because it needs no archived forecasts. Every system is "
        f"scored on the same cases from {doc['test'][0]} to {doc['test'][1]}.",
        "",
        "Skill is 1 - CRPS/reference; brackets are 95% intervals from resampling whole days. emos_multi is EMOS "
        "given the same extra models as gnostiq.",
        "",
    ]
    for var in dict.fromkeys(r["var"] for r in doc["rows"]):
        rows = [r for r in doc["rows"] if r["var"] == var]
        refs = [x for x in REFS if x in rows[0]["skill"]]
        systems = [x for x in ("clim", "emos", "emos_multi", "gnostiq") if x in rows[0]["crps"]]
        out += [
            f"## {var}",
            "",
            "| training | weeks | pairs | " + " | ".join(f"CRPS {s}" for s in systems) + " | "
            + " | ".join(f"vs {x}" for x in refs) + " |",
            "|---" * (3 + len(systems) + len(refs)) + "|",
        ]  # fmt: skip
        for r in rows:
            cells = [r["size"], str(r["weeks"]), f"{r['pairs']:,}"]
            cells += [f"{r['crps'][s]:.3f}" for s in systems]
            cells += [verify.skill_cell(r["skill"][x]) for x in refs]
            out.append("| " + " | ".join(cells) + " |")
        out.append("")
    return "\n".join(out)
