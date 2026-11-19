"""gnostiq command line."""

import argparse
import logging

from gnostiq import cfg

log = logging.getLogger("gnostiq")
# commands that need the site's own record
OWN = {"build", "baselines", "train", "curve", "verify", "cases", "all"}

SOURCES = ["static", "station", "nwp", "precip"]
# pulled only when named
OPTIONAL = []
OPTIONAL = ["tamsat", "nimet"]


def pull(c, a):
    from gnostiq.ingest import nwp, precip, static, station

    mods = {"static": static, "station": station, "nwp": nwp, "precip": precip}
    from gnostiq.ingest import nimet, tamsat

    mods.update(tamsat=tamsat, nimet=nimet)
    only = a.only.split(",") if a.only else SOURCES
    if c.donor and not a.only:
        # a site on borrowed networks needs only its own terrain height
        only = ["static"]
    bad = [s for s in only if s not in mods]
    if bad:
        raise SystemExit(f"unknown source {bad}; choose from {SOURCES + OPTIONAL}")
    for s in only:
        # chirps only matters when it is the rain truth
        if s == "precip" and c.truth.rain != "chirps" and not a.only:
            continue
        mods[s].pull(c, refresh=a.refresh)


def build(c, a):
    from gnostiq import align, qc
    from gnostiq.ingest import nwp, station

    station.build(c)
    nwp.build(c)
    qc.run(c)
    align.build(c)


def baselines(c, a):
    from gnostiq import baselines

    baselines.run(c)


def train(c, a):
    from gnostiq import train

    train.run(c)


def curve(c, a):
    from gnostiq import curve

    curve.run(c)


def verify(c, a):
    from gnostiq import verify

    verify.run(c)


def cases(c, a):
    from gnostiq import cases

    cases.run(c)


def each(c, a, fn):
    if not a.all_sites:
        return fn(c)
    bad = []
    for x in cfg.sites(c):
        x.paths.ensure()
        try:
            fn(x)
        except Exception:
            # one site failing must not stop the others
            log.exception("%s failed for %s", a.cmd, x.site.name)
            bad.append(x.site.name)
    if bad:
        raise SystemExit(f"{a.cmd} failed for {', '.join(bad)}")


def run(c, a):
    from gnostiq import run

    each(c, a, run.run)


def check(c, a):
    from gnostiq import live

    each(c, a, lambda x: live.run(x, a.days))


def season(c, a):
    from gnostiq import season

    each(c, a, lambda x: season.run(x, a.start, a.end))


def publish(c, a):
    from gnostiq import publish

    each(c, a, lambda x: publish.run(x, a.days))


def verify_record(c, a):
    from gnostiq import publish

    rows = publish.verify(a.cid, a.depth)
    for r in rows:
        print(f"{'ok' if r['ok'] else 'FAILED':6} {r['site']:10} issued {r['issued_utc']}  record {r['record']}",
              *r["problems"], sep="  ")  # fmt: skip
    bad = sum(not r["ok"] for r in rows)
    print(f"{len(rows)} records checked, {bad} failed")
    if bad:
        raise SystemExit(1)


def everything(c, a):
    for step in (build, baselines, train, verify, cases):
        step(c, a)


def serve(c, a):
    import uvicorn

    from gnostiq import api

    uvicorn.run(api.create(c), host=a.host, port=a.port, log_level="info")


def main(argv=None):
    p = argparse.ArgumentParser(prog="gnostiq")
    p.add_argument("--config", help=f"config file (default: {cfg.FILENAME} found upward, or $GNOSTIQ_CFG)")
    p.add_argument("--site", help="site table in the config (default: the first, or $GNOSTIQ_SITE)")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add(name, fn, text):
        s = sub.add_parser(name, help=text)
        s.set_defaults(fn=fn)
        return s

    s = add("pull", pull, "download raw data (cached; safe to re-run)")
    s.add_argument("--only", help=f"comma-separated subset of {','.join(SOURCES + OPTIONAL)}")
    s.add_argument("--refresh", action="store_true", help="re-download files that change over time")
    add("build", build, "parse raw files into the working tables")
    add("baselines", baselines, "fit the reference forecasts")
    add("train", train, "fit the correction networks")
    add("curve", curve, "learning curve: skill against archive length (a few minutes)")
    add("verify", verify, "write the scorecard for the test window")
    add("cases", cases, "write the heavy-rain case replays")
    add("all", everything, "build, baselines, train, verify, cases")
    s = add("run", run, "fetch the latest forecast and write forecast.json")
    s.add_argument("--all-sites", action="store_true", help="every site in the config")
    k = add("check", check, "score past forecasts against reports that came in since")
    k.add_argument("--days", type=int, default=30)
    k.add_argument("--all-sites", action="store_true", help="every site in the config")
    s = add("publish", publish, "store each day's first forecast and its record on Auto Drive")
    s.add_argument("--days", type=int, default=3, help="catch up missed days this far back")
    s.add_argument("--all-sites", action="store_true", help="every site in the config")
    s = add("verify-record", verify_record, "check a published record, and the ones before it, from Auto Drive")
    s.add_argument("cid", help="CID of a record")
    s.add_argument("--depth", type=int, help="stop after this many records")
    s = add("season", season, "score a past season against NiMet reports (default: the latest wet season)")
    s.add_argument("--start", help="first day, YYYY-MM-DD")
    s.add_argument("--end", help="last day, YYYY-MM-DD")
    s.add_argument("--all-sites", action="store_true", help="every site in the config")
    s = add("serve", serve, "serve the API and web page")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8000)

    a = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    if a.cmd == "verify-record":
        # anyone can check a record; it needs no config
        return a.fn(None, a)
    c = cfg.load(a.config, a.site) if a.config or a.site else cfg.get()
    if c.donor and a.cmd in OWN:
        raise SystemExit(
            f"{c.site.name} runs the networks trained for {c.donor} and has no record of its own to {a.cmd}"
        )
    c.paths.ensure()
    a.fn(c, a)


if __name__ == "__main__":
    main()
