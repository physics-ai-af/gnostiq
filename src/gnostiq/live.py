"""Live check: score the forecasts the page showed against reports that came in afterwards."""

import json
import logging

import numpy as np
import pandas as pd

from gnostiq import dist, verify
from gnostiq.ingest import station
from gnostiq.io import fetch

log = logging.getLogger("gnostiq")

DAYS = 30
OBS = {"t2m": "t", "td2m": "td"}
HOUR = 3600


def archive(c):
    parts = sorted(c.paths.archive.glob("*.parquet"))
    if not parts:
        raise FileNotFoundError(f"no issued forecasts in {c.paths.archive}; run `gnostiq run` first")
    a = pd.concat([pd.read_parquet(p) for p in parts], ignore_index=True)
    # one issue per UTC day, the first, so a day of 3-hourly runs counts once
    day = a.init.dt.floor("D")
    return a[a.init == a.groupby(day).init.transform("min")].reset_index(drop=True)


def reports(c, since, until):
    path = c.paths.raw / "station" / f"iem_{c.site.icao}_live.csv"
    params = {
        "station": c.site.icao,
        "data": ["tmpf", "dwpf", "alti", "mslp", "sknt"],
        "sts": f"{since:%Y-%m-%dT%H:%MZ}",
        "ets": f"{until + pd.Timedelta(hours=1):%Y-%m-%dT%H:%MZ}",
        "tz": "Etc/UTC",
        "format": "onlycomma",
        "missing": "M",
        "report_type": [3, 4],
    }
    fetch(station.IEM, path, params, max_age=HOUR)
    o, _ = station.read_iem([path])
    # the same gross limits the training truth went through
    ok_t = o.t.between(-10, 50)
    o = o.assign(t=o.t.where(ok_t), td=o.td.where(ok_t & o.td.between(-40, 40) & (o.td <= o.t + 0.5)))
    rows = [o[col].rename("obs").to_frame().assign(var=var) for var, col in OBS.items()]
    return pd.concat(rows).rename_axis("valid").reset_index().dropna(subset=["obs"])


def score(j):
    point = j.sigma.isna()
    err = np.abs(j.mu - j.obs).to_numpy(float)
    crps = np.where(
        point, err, dist.crps_norm(j.obs.to_numpy(float), j.mu.to_numpy(float), j.sigma.fillna(1).to_numpy(float))
    )
    return j.assign(err=err, crps=crps)


def run(c, days=DAYS):
    a = archive(c)
    until = pd.Timestamp.now("UTC").tz_localize(None).floor("h")
    since = until - pd.Timedelta(days=days)
    a = a[(a.valid >= since) & (a.valid <= until)]
    rep = reports(c, since, until)
    j = score(a.merge(rep, on=["valid", "var"]))

    # a case counts only if every core system forecast it; ICON's missing day 7 only shrinks its own n
    core = [s for s in ("gnostiq", "raw", "clim") if s in set(j.system)]
    key = ["init", "valid", "var"]
    n = j[j.system.isin(core)].groupby(key).system.nunique()
    j = j.merge(n[n == len(core)].reset_index()[key], on=key)
    rng = np.random.default_rng(0)

    out = {"site": c.site.name, "base": c.nwp.base, "since": f"{since:%Y-%m-%d}", "until": f"{until:%Y-%m-%dT%H:%MZ}",
           "issues": int(a.init.nunique()), "reports": int(rep.valid.nunique()), "vars": {}}  # fmt: skip
    # the height correction alone; older archives lack it, so it is scored where present
    refs = [s for s in ("raw", "lapse", "clim") if s in set(j.system)]
    for var in OBS:
        v = j[j["var"] == var]
        systems = {}
        for s, g in v.groupby("system"):
            systems[s] = {"n": len(g), "bias": float((g.mu - g.obs).mean()), "mae": float(g.err.mean()),
                          "crps": float(g.crps.mean())}  # fmt: skip
        mine = v[v.system == "gnostiq"].set_index(["init", "valid"]).crps
        day = mine.index.get_level_values("valid").floor("D")
        skill = {}
        for ref in refs:
            theirs = v[v.system == ref].set_index(["init", "valid"]).crps.reindex(mine.index)
            ok = theirs.notna().to_numpy()
            skill[ref] = verify.boot_skill(day[ok], mine.to_numpy()[ok], theirs.to_numpy()[ok], rng)
        daily = v.assign(day=v.valid.dt.strftime("%Y-%m-%d")).pivot_table(index="day", columns="system", values="err")
        out["vars"][var] = {
            "cases": int(len(mine)),
            "systems": systems,
            "skill": skill,
            "daily": [
                {"day": d, **{k: round(float(x), 2) for k, x in r.items() if pd.notna(x)}} for d, r in daily.iterrows()
            ],
        }

    c.paths.reports.mkdir(parents=True, exist_ok=True)
    (c.paths.reports / "live.json").write_text(json.dumps(out, indent=1))
    (c.paths.reports / "live.md").write_text(markdown(out))
    log.info("live check: %d issues, %d reports, %d temperature cases since %s", out["issues"], out["reports"],
             out["vars"]["t2m"]["cases"], out["since"])  # fmt: skip
    return out


def markdown(doc):
    out = [
        f"# Live check: {doc['site']}",
        "",
        "Forecasts as the page showed them, first issue of each UTC day, scored against airport reports from "
        f"{doc['since']} to {doc['until']}. Reports are whole degrees, which adds about 0.3 C of noise to every "
        "system.",
        "",
        "Skill is 1 - CRPS/reference; brackets are 95% intervals from resampling whole days. Raw models are scored "
        "as single values, so their CRPS is their absolute error.",
        "",
        f"{doc['issues']} days of forecasts, {doc['reports']} reports.",
        "",
    ]
    for var, v in doc["vars"].items():
        out += [f"## {var} ({v['cases']} cases)", "", "| system | n | bias | MAE | CRPS |", "|---|---|---|---|---|"]
        for s, r in sorted(v["systems"].items()):
            out.append(f"| {s} | {r['n']} | {r['bias']:+.2f} | {r['mae']:.2f} | {r['crps']:.2f} |")
        out.append("")
        for ref, sk in v["skill"].items():
            out.append(f"CRPSS vs {ref}: {verify.skill_cell(sk)}")
        out.append("")
    return "\n".join(out)
