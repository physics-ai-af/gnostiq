import importlib.util
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from conftest import NEARBY, add_nearby, write_cfg

from gnostiq import cfg

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("seed_state", ROOT / "scripts" / "seed_state.py")
seed = importlib.util.module_from_spec(spec)
spec.loader.exec_module(seed)


def two_sites(tmp_path):
    c = cfg.load(write_cfg(tmp_path, {'data = "data"': 'data = "data/jos"'}))
    near = add_nearby(tmp_path, NEARBY.replace('data = "nearby"', 'data = "data/nearby"'))
    for x in (c, near):
        x.paths.ensure()
        (x.paths.reports / "forecast.json").write_text("{}")
        (x.paths.archive / "20261119T00.json.gz").write_bytes(b"gz")
        (x.paths.raw / "big.grib").write_bytes(b"raw")
        (x.paths.processed / "static.json").write_text("{}")
        (x.paths.processed / "pairs_hourly.parquet").write_bytes(b"pairs")
    (c.paths.models / "hourly.pt").write_bytes(b"net")
    (c.paths.interim / "obs.parquet").write_bytes(b"obs")
    (c.paths.interim / "hourly.parquet").write_bytes(b"table")
    (c.paths.data / "published").mkdir()
    (c.paths.data / "published" / "2026-11-19.record.json").write_text("{}")
    return cfg.load(c.source)


def test_only_what_the_workflow_needs_is_copied(tmp_path):
    c = two_sites(tmp_path)
    out = tmp_path / "out"
    got = seed.collect(c, out)
    assert "jos/models" in got and "nearby/reports" in got and "jos/published" in got
    kept = [
        "jos/models/hourly.pt",
        "jos/interim/obs.parquet",
        "jos/processed/static.json",
        "jos/archive/20261119T00.json.gz",
        "nearby/reports/forecast.json",
        "nearby/processed/static.json",
    ]
    for f in kept:
        assert (out / f).exists(), f
    for f in ("jos/raw", "jos/interim/hourly.parquet", "jos/processed/pairs_hourly.parquet", "nearby/models"):
        assert not (out / f).exists(), f


@pytest.mark.skipif(not shutil.which("git"), reason="needs git")
def test_the_branch_ignore_keeps_later_runs_to_the_same_files(tmp_path):
    out = tmp_path / "out"
    seed.collect(two_sites(tmp_path), out)
    subprocess.run(["git", "init", "-q"], cwd=out, check=True)
    for f in ("jos/raw/station/iem_DNJO_live.csv", "jos/raw/nimet/x.json", "jos/interim/hourly.parquet",
              "jos/processed/pairs_hourly.parquet"):  # fmt: skip
        assert subprocess.run(["git", "check-ignore", "-q", f], cwd=out).returncode == 0, f
    for f in ("jos/processed/static.json", "jos/interim/obs.parquet", "jos/archive/x.parquet", "jos/reports/live.json"):
        assert subprocess.run(["git", "check-ignore", "-q", f], cwd=out).returncode == 1, f


@pytest.mark.skipif(not shutil.which("git"), reason="needs git")
def test_update_adds_to_the_branch_without_replacing_it(tmp_path, monkeypatch):
    for k in ("AUTHOR", "COMMITTER"):
        monkeypatch.setenv(f"GIT_{k}_NAME", "t")
        monkeypatch.setenv(f"GIT_{k}_EMAIL", "t@example.com")
    c = two_sites(tmp_path)
    remote = tmp_path / "remote.git"
    for args, where in ((["init", "-q", "--bare", str(remote)], tmp_path), (["init", "-q"], tmp_path),
                        (["remote", "add", "origin", str(remote)], tmp_path)):  # fmt: skip
        subprocess.run(["git", *args], cwd=where, check=True)
    cfg_arg = ["--config", str(c.source)]
    seed.main(cfg_arg)
    with pytest.raises(SystemExit, match="already exists"):
        seed.main(cfg_arg)
    (c.paths.reports / "season.json").write_text('{"window": 1}')
    seed.main([*cfg_arg, "--update", "reports/season.json"])

    def at_remote(*args):
        return subprocess.run(["git", *args], cwd=remote, check=True, capture_output=True, text=True).stdout

    assert at_remote("log", "--format=%s", "state").split("\n")[:2] == ["state: update reports/season.json",
                                                                          "state: seed from data/"]  # fmt: skip
    assert "jos/models/hourly.pt" in at_remote("ls-tree", "-r", "--name-only", "state")
    assert at_remote("show", "state:jos/reports/season.json") == '{"window": 1}'
    with pytest.raises(SystemExit, match="not kept on state"):
        seed.main([*cfg_arg, "--update", "raw/big.grib"])


def test_a_site_outside_data_is_refused(tmp_path):
    c = cfg.load(write_cfg(tmp_path))
    add_nearby(tmp_path)
    with pytest.raises(SystemExit, match="nearby: data directory .* is not under"):
        seed.collect(c, tmp_path / "out")


def test_the_live_workflow_only_runs_commands_that_exist():
    text = (ROOT / ".github" / "workflows" / "live.yml").read_text()
    used = set(re.findall(r"gnostiq (\w[\w-]*)", text))
    assert used == {"run", "publish", "check", "export"}
    from gnostiq import cli

    for cmd in used:
        with pytest.raises(SystemExit) as e:
            cli.main([cmd, "--help"])
        assert e.value.code == 0
    # the state branch is checked out where the configs point
    assert "ref: state" in text and "path: data" in text and "next:state" in text
