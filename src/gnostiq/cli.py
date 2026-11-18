"""gnostiq command line."""

import argparse
import logging

from gnostiq import cfg

log = logging.getLogger("gnostiq")
# commands that need the site's own record
OWN = {"build", "baselines", "train", "curve", "verify", "cases", "all"}

SOURCES = ["static", "station", "nwp", "precip"]


def pull(c, a):
    from gnostiq.ingest import nwp, precip, static, station

    mods = {"static": static, "station": station, "nwp": nwp, "precip": precip}
    only = a.only.split(",") if a.only else SOURCES
    if c.donor and not a.only:
        # a site on borrowed networks needs only its own terrain height
        only = ["static"]
    bad = [s for s in only if s not in mods]
    if bad:
        raise SystemExit(f"unknown source {bad}; choose from {SOURCES}")
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
    sub = p.add_subparsers(dest="cmd", required=True)

    def add(name, fn, text):
        s = sub.add_parser(name, help=text)
        s.set_defaults(fn=fn)
        return s

    s = add("pull", pull, "download raw data (cached; safe to re-run)")
    s.add_argument("--only", help=f"comma-separated subset of {','.join(SOURCES)}")
    s.add_argument("--refresh", action="store_true", help="re-download files that change over time")
    add("build", build, "parse raw files into the working tables")
    add("baselines", baselines, "fit the reference forecasts")
    add("train", train, "fit the correction networks")
    add("curve", curve, "learning curve: skill against archive length (a few minutes)")
    add("verify", verify, "write the scorecard for the test window")
    add("cases", cases, "write the heavy-rain case replays")
    add("all", everything, "build, baselines, train, verify, cases")
    s = add("run", run, "fetch the latest forecast and write forecast.json")
    s.add_argument("--all-sites", action="store_true", help="every gnostiq*.toml beside the config")
    k = add("check", check, "score past forecasts against reports that came in since")
    k.add_argument("--days", type=int, default=30)
    k.add_argument("--all-sites", action="store_true", help="every gnostiq*.toml beside the config")
    s = add("serve", serve, "serve the API and web page")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8000)

    a = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    c = cfg.load(a.config) if a.config else cfg.get()
    if c.donor and a.cmd in OWN:
        raise SystemExit(
            f"{c.site.name} runs the networks trained for {c.donor} and has no record of its own to {a.cmd}"
        )
    c.paths.ensure()
    a.fn(c, a)


if __name__ == "__main__":
    main()
