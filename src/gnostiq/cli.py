"""gnostiq command line."""

import argparse
import logging

from gnostiq import cfg

SOURCES = ["station"]


def pull(c, a):
    from gnostiq.ingest import station

    mods = {"station": station}
    only = a.only.split(",") if a.only else SOURCES
    bad = [s for s in only if s not in mods]
    if bad:
        raise SystemExit(f"unknown source {bad}; choose from {SOURCES}")
    for s in only:
        mods[s].pull(c, refresh=a.refresh)


def build(c, a):
    from gnostiq.ingest import station

    station.build(c)


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

    a = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    c = cfg.get()
    c.paths.ensure()
    a.fn(c, a)


if __name__ == "__main__":
    main()
