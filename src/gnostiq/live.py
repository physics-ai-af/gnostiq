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
RECENT = 7
# local hours that hold the day's high and its low; NiMet reports some days only by day, so a
# high or low needs this many reported hours in its window rather than a full day of reports
HIGH = (11, 17)
LOW = (4, 8)
ENOUGH = 2
WINDOWS = {"high": list(HIGH), "low": list(LOW), "enough": ENOUGH}
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


def val(x, nd=1):
    return None if pd.isna(x) else round(float(x), nd)


def by_day(w, tz):
    # one row per local day: high, low and average error over the reported hours, so every
    # system is judged on the same hours as the report
    t = w[w["var"] == "t2m"].dropna(subset=["obs", "gnostiq"])
    if t.empty:
        return []
    local = t.valid.dt.tz_localize("UTC").dt.tz_convert(tz)
    t = t.assign(day=local.dt.strftime("%Y-%m-%d"), hour=local.dt.hour)
    band = "q10" in t and "q90" in t
    rows = []
    for d, h in t.groupby("day"):
        row = {"day": d, "hours": len(h)}
        for name, (lo, hi), pick in (("max", HIGH, "max"), ("min", LOW, "min")):
            x = h[h.hour.between(lo, hi)]
            for col in ("obs", "gnostiq", "raw"):
                row[f"{col}_{name}"] = val(getattr(x[col], pick)()) if len(x) >= ENOUGH and col in x else None
        for col in ("gnostiq", "raw"):
            row[f"{col}_err"] = val((h[col] - h.obs).abs().mean(), 2) if col in h else None
        if band:
            b = h.dropna(subset=["q10", "q90"])
            row["in_n"], row["in_k"] = len(b), int(((b.obs >= b.q10) & (b.obs <= b.q90)).sum())
        rows.append(row)
    return rows


def tally(rows):
    out = {"days": len(rows)}
    for k in ("max", "min"):
        x = [r for r in rows if r[f"obs_{k}"] is not None]
        out[k] = {"days": len(x)}
        for s in ("gnostiq", "raw"):
            e = [abs(r[f"{s}_{k}"] - r[f"obs_{k}"]) for r in x if r[f"{s}_{k}"] is not None]
            if e:
                # values are rounded to 0.1, so allow for it at the 1 degree line
                out[k][s] = {"n": len(e), "mae": round(sum(e) / len(e), 2),
                             "within1": round(sum(v <= 1.0001 for v in e) / len(e), 3)}  # fmt: skip
    out["inside"] = {"n": sum(r.get("in_n", 0) for r in rows), "k": sum(r.get("in_k", 0) for r in rows)}
    return out


def merge_days(old, new):
    # a day seen again keeps whichever version saw more reported hours
    rows = {r["day"]: r for r in old}
    for r in new:
        if r["day"] not in rows or r["hours"] >= rows[r["day"]]["hours"]:
            rows[r["day"]] = r
    return [rows[d] for d in sorted(rows)]


def track(c, a, rep, old):
    # every day the page has forecast, the forecast made up to a day before, with the public record behind it
    a = a[(a.lead_day == 1) & a.system.isin(["gnostiq", "raw"])]
    a = a.sort_values("init").drop_duplicates(["valid", "var", "system"], keep="last")
    w = a.pivot_table(index=["valid", "var"], columns="system", values="mu")
    g = a[a.system == "gnostiq"].set_index(["valid", "var"])
    w = w.join(g[[k for k in ("q10", "q90", "init") if k in g]], how="left")
    w = w.join(rep.set_index(["valid", "var"]).obs, how="left").reset_index()
    rows = by_day(w, c.site.tz)
    path = c.paths.reports / "records.json"
    cids = {r["day"]: r["record_cid"] for r in json.loads(path.read_text()).get("records", [])} if path.exists() else {}
    if "init" in w:
        t = w[w["var"] == "t2m"].dropna(subset=["obs", "gnostiq"])
        day = t.valid.dt.tz_localize("UTC").dt.tz_convert(c.site.tz).dt.strftime("%Y-%m-%d")
        made = t.groupby(day).init.agg(lambda s: s.mode().iloc[0])
        for r in rows:
            init = made.get(r["day"])
            r["issued_utc"] = None if init is None else f"{init:%Y-%m-%dT%H:%MZ}"
            r["record"] = None if init is None else cids.get(f"{init:%Y-%m-%d}")
    rows = merge_days(old, rows)
    return {"tz": c.site.tz, "windows": WINDOWS, "rows": rows, "summary": tally(rows)}


def recent(c, a, rep, until, days=RECENT):
    # the day-ahead forecast as the page showed it, hour by hour, next to what was reported
    a = a[(a.lead_day == 1) & (a.valid > until - pd.Timedelta(days=days)) & a.system.isin(["gnostiq", "raw", "lapse"])]
    a = a.sort_values("init").drop_duplicates(["valid", "var", "system"], keep="last")

    def shown(col, sign):
        # archives from before the band was saved fall back to the symmetric one
        q = a[col] if col in a else pd.Series(np.nan, index=a.index)
        return q.fillna(a.mu + sign * dist.Z80 * a.sigma)

    a = a.assign(q10=shown("q10", -1), q90=shown("q90", 1))
    g = a[a.system == "gnostiq"].set_index(["valid", "var"])[["q10", "mu", "q90"]].rename(columns={"mu": "q50"})
    w = g.join(a[a.system != "gnostiq"].pivot_table(index=["valid", "var"], columns="system", values="mu"), how="outer")
    w = w.join(rep.set_index(["valid", "var"]).obs, how="left").reset_index()

    hourly = []
    for v, h in w.groupby("valid"):
        row = {"valid_utc": f"{v:%Y-%m-%dT%H:%MZ}"}
        for _, r in h.iterrows():
            row[r["var"]] = {k: val(r.get(k)) for k in ("obs", "q10", "q50", "q90", "raw", "lapse")}
        hourly.append(row)

    inside = {}
    for var, h in w.dropna(subset=["obs", "q10", "q90"]).groupby("var"):
        inside[var] = {"n": len(h), "k": int(((h.obs >= h.q10) & (h.obs <= h.q90)).sum())}

    days_ = by_day(w.rename(columns={"q50": "gnostiq"}), c.site.tz)
    daily = [d for d in days_ if d["obs_max"] is not None or d["obs_min"] is not None]
    return {"days": days, "tz": c.site.tz, "hourly": hourly, "inside": inside, "daily": daily, "windows": WINDOWS}


def earlier(c):
    path = c.paths.reports / "live.json"
    try:
        return json.loads(path.read_text()).get("track", {}).get("rows", [])
    except (OSError, ValueError, AttributeError):
        return []


def run(c, days=DAYS):
    old = earlier(c)
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
           "sources": sources(rep), "vars": out_vars, "recent": recent(c, a, rep, until),
           "track": track(c, a, rep, old)}  # fmt: skip
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
    out += track_md(doc.get("track"), "day-ahead forecast as the page showed it")
    r = doc.get("recent") or {}
    if r.get("inside"):
        out += [f"## Last {r['days']} days, day-ahead forecast against reports", ""]
        for var, x in r["inside"].items():
            out.append(f"- {var}: report inside Gnostiq's 80% range {x['k']} of {x['n']} times (expect about 80%)")
        if r["daily"]:
            out += ["", f"Highs and lows over the reported hours ({r['tz']} days):", "",
                    "| day | hours | reported | Gnostiq | raw |", "|---|---|---|---|---|"]  # fmt: skip
            for d in r["daily"]:
                cells = [f"{d[f'{k}_max']} / {d[f'{k}_min']}" for k in ("obs", "gnostiq", "raw")]
                out.append(f"| {d['day']} | {d['hours']} | " + " | ".join(cells) + " |")
        out.append("")
    return "\n".join(out)


def track_md(t, what):
    if not t or not t["rows"]:
        return []
    s, w = t["summary"], t["windows"]
    hi, lo = w["high"], w["low"]
    out = [f"## Track record: {s['days']} days, {what}", "",
           f"High from {hi[0]:02d}:00 to {hi[1]:02d}:00 and low from {lo[0]:02d}:00 to {lo[1]:02d}:00 local time, "
           f"over the hours reported (at least {w['enough']} in each).", ""]  # fmt: skip
    for k, name in (("max", "High"), ("min", "Low")):
        x = s[k]
        for sys in ("gnostiq", "raw"):
            if sys in x:
                out.append(f"- {name}, {sys}: average error {x[sys]['mae']:.2f} C, within 1 C on "
                           f"{x[sys]['within1']:.0%} of {x[sys]['n']} days")  # fmt: skip
    if s["inside"]["n"]:
        i = s["inside"]
        out.append(f"- Reports inside Gnostiq's 80% range: {i['k']} of {i['n']} hours ({i['k'] / i['n']:.0%})")
    return [*out, ""]
