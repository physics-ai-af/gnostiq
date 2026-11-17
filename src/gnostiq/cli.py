"""gnostiq command line."""

import argparse
import logging

from gnostiq import cfg

SOURCES = ["static", "station", "nwp", "precip"]


def pull(c, a):
    from gnostiq.ingest import nwp, precip, static, station

    mods = {"static": static, "station": station, "nwp": nwp, "precip": precip}
    only = a.only.split(",") if a.only else SOURCES
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


def main(argv=None):
    p = argparse.ArgumentParser(prog="gnostiq")
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

    a = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    c = cfg.get()
    c.paths.ensure()
    a.fn(c, a)


if __name__ == "__main__":
    main()
