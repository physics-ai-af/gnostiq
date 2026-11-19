"""Live check: score the forecasts the page showed against reports that came in afterwards."""

import json
import logging

import numpy as np
import pandas as pd
import requests

from gnostiq import dist, verify
from gnostiq.ingest import nimet, station
from gnostiq.io import Missing, fetch

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


def metars(c, since, until):
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
    return long(o, "iem")


def synops(c, since, until):
    o, _ = nimet.obs(c, since, until)
    return long(o, "nimet")


def long(o, source):
    rows = [o[col].rename("obs").to_frame().assign(var=var) for var, col in OBS.items()]
    out = pd.concat(rows).rename_axis("valid").reset_index().dropna(subset=["obs"])
    return out.assign(source=source)


def reports(c, since, until):
    got, err = [], None
    # synops first: 0.1 C against whole-degree METARs
    for f in (synops, metars):
        try:
            got.append(f(c, since, until))
        except (requests.RequestException, Missing, ValueError, OSError) as e:
            log.warning("%s unavailable: %s", f.__name__, e)
            err = e
    if not got:
        raise err
    r = pd.concat(got, ignore_index=True)
    return r.drop_duplicates(["valid", "var"], keep="first").reset_index(drop=True)


def score(j):
    point = j.sigma.isna()
    err = np.abs(j.mu - j.obs).to_numpy(float)
    crps = np.where(
        point, err, dist.crps_norm(j.obs.to_numpy(float), j.mu.to_numpy(float), j.sigma.fillna(1).to_numpy(float))
    )
    return j.assign(err=err, crps=crps)


def sources(rep):
    if "source" not in rep:
        return {}
    return {k: int(v) for k, v in rep.groupby("source").valid.nunique().items()}


def summarize(j, key, core, refs, rng):
    # a case counts only if every core system forecast it; a model missing some leads only shrinks its own n
    core = [s for s in core if s in set(j.system)]
    n = j[j.system.isin(core)].groupby([*key, "var"]).system.nunique()
    j = j.merge(n[n == len(core)].reset_index()[[*key, "var"]], on=[*key, "var"])
    out = {}
    for var in OBS:
        v = j[j["var"] == var]
        systems = {}
        for s, g in v.groupby("system"):
            systems[s] = {"n": len(g), "bias": float((g.mu - g.obs).mean()), "mae": float(g.err.mean()),
                          "crps": float(g.crps.mean())}  # fmt: skip
        mine = v[v.system == "gnostiq"].set_index(key).crps
        day = mine.index.get_level_values("valid").floor("D")
        skill = {}
        for ref in refs:
            if ref not in systems:
                continue
            theirs = v[v.system == ref].set_index(key).crps.reindex(mine.index)
            ok = theirs.notna().to_numpy()
            skill[ref] = verify.boot_skill(day[ok], mine.to_numpy()[ok], theirs.to_numpy()[ok], rng)
        out[var] = {"cases": int(len(mine)), "systems": systems, "skill": skill}
    return out, j


def run(c, days=DAYS):
    a = archive(c)
    until = pd.Timestamp.now("UTC").tz_localize(None).floor("h")
    since = until - pd.Timedelta(days=days)
    a = a[(a.valid >= since) & (a.valid <= until)]
    rep = reports(c, since, until)
    j = score(a.merge(rep, on=["valid", "var"]))
    # the height correction alone; older archives lack it, so it is scored where present
    out_vars, j = summarize(j, ["init", "valid"], ["gnostiq", "raw", "clim"], ["raw", "lapse", "clim"],
                            np.random.default_rng(0))  # fmt: skip
    for var, v in out_vars.items():
        g = j[j["var"] == var]
        daily = g.assign(day=g.valid.dt.strftime("%Y-%m-%d")).pivot_table(index="day", columns="system", values="err")
        v["daily"] = [{"day": d, **{k: round(float(x), 2) for k, x in r.items() if pd.notna(x)}}
                      for d, r in daily.iterrows()]  # fmt: skip

    out = {"site": c.site.name, "base": c.nwp.base, "since": f"{since:%Y-%m-%d}", "until": f"{until:%Y-%m-%dT%H:%MZ}",
           "issues": int(a.init.nunique()), "reports": int(rep.valid.nunique()),
           "sources": sources(rep), "vars": out_vars}  # fmt: skip
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
        "Forecasts as the page showed them, first issue of each UTC day, scored against station reports from "
        f"{doc['since']} to {doc['until']}: NiMet synops (0.1 C) where they exist, airport METARs (whole degrees) "
        "otherwise.",
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
