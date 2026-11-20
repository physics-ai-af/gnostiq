"""Puts what the live workflow needs from data/ on the state branch, once; later, adds single files to it."""

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from gnostiq import cfg

BRANCH = "state"
# per site; raw downloads and training tables stay on this machine
KEEP = ["models", "reports", "processed/static.json", "interim/obs.parquet", "archive", "published"]
IGNORE = """\
*/raw/
*/processed/*
!*/processed/static.json
*/interim/*
!*/interim/obs.parquet
"""


def collect(c, out, parts=KEEP):
    # the branch is checked out as data/, so each site keeps its path below data/
    root = c.source.parent / "data"
    copied = []
    for x in cfg.sites(c):
        try:
            rel = x.paths.data.relative_to(root)
        except ValueError:
            raise SystemExit(f"{x.site.name}: data directory {x.paths.data} is not under {root}") from None
        for part in parts:
            src = x.paths.data / part
            if not src.exists():
                continue
            dst = out / rel / part
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.is_dir():
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dst)
            copied.append(f"{rel.as_posix()}/{part}")
    if parts is KEEP:
        (out / ".gitignore").write_text(IGNORE)
    return copied


def git(*args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def update(c, url, parts):
    # on top of the branch the workflow keeps, never replacing it
    bad = [p for p in parts if not any(p == k or p.startswith(k.rstrip("/") + "/") for k in KEEP)]
    if bad:
        sys.exit(f"not kept on {BRANCH}: {', '.join(bad)}; parts must fall under {', '.join(KEEP)}")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        git("clone", "-q", "--depth", "1", "-b", BRANCH, url, tmp, cwd=c.source.parent)
        files = collect(c, Path(tmp), parts)
        if not files:
            sys.exit("none of those exist under data/")
        git("add", "-A", cwd=tmp)
        if not git("status", "--porcelain", cwd=tmp):
            print(f"{BRANCH} already has these")
            return
        git("commit", "-qm", f"state: update {' '.join(parts)}", cwd=tmp)
        git("push", "-q", "origin", BRANCH, cwd=tmp)
    # a run already under way force-pushes its own copy and would drop this
    print(f"added to {BRANCH}:", *files, sep="\n  ")
    print("If a live run was in progress, run this again once it has finished.")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", help="path to gnostiq.toml")
    p.add_argument("--out", help="only copy the files here; no git")
    p.add_argument("--remote", default="origin")
    p.add_argument("--force", action="store_true", help="replace a state branch that already exists")
    p.add_argument("--update", nargs="+", metavar="PART", help="add only these, e.g. reports/season.json")
    a = p.parse_args(argv)
    c = cfg.load(a.config)
    if a.out:
        for f in collect(c, Path(a.out), a.update or KEEP):
            print(f)
        return
    url = git("remote", "get-url", a.remote, cwd=c.source.parent)
    if a.update:
        update(c, url, a.update)
        return
    exists = subprocess.run(["git", "ls-remote", "--exit-code", "--heads", url, BRANCH], capture_output=True)
    if exists.returncode == 0 and not a.force:
        # the workflow's copy has the newer archive and the record chain; overwriting it breaks the chain
        sys.exit(f"{BRANCH} already exists on {a.remote}. Use --force only if nothing has been published from it.")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        files = collect(c, Path(tmp))
        if not any(f.endswith("/models") for f in files):
            sys.exit("no trained models under data/; run `gnostiq all` first")
        git("init", "-q", "-b", BRANCH, cwd=tmp)
        git("add", "-A", cwd=tmp)
        git("commit", "-qm", "state: seed from data/", cwd=tmp)
        git("push", "-fq", url, BRANCH, cwd=tmp)
    print(f"pushed {len(files)} paths to {BRANCH}:", *files, sep="\n  ")


if __name__ == "__main__":
    main()
