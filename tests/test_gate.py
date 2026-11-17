import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
import synth
from conftest import SMALL, SYNTH_END, write_cfg

from gnostiq import cfg

GATE = Path(__file__).resolve().parents[1] / "scripts" / "gate.py"


def gate(c, *args):
    env = {**os.environ, "GNOSTIQ_CFG": str(c.source)}
    r = subprocess.run([sys.executable, str(GATE), *args], env=env, capture_output=True, text=True)
    return r, c.paths.reports / "gate.md"


def test_good_temperature_record_without_gauge_is_partial(station_raw):
    r, report = gate(station_raw)
    assert r.returncode == 0, r.stderr
    assert r.stdout.startswith("PARTIAL. Temperature truth: NIM00065134")
    text = report.read_text()
    for part in ("## GHCNh records near the site", "## GHCNh NIM00065134", "Location history",
                 "Monthly synoptic-slot coverage", "barometer elevation", "vs DNJO METAR", "## Gate"):  # fmt: skip
        assert part in text, part
    assert 'truth.temp = "ghcnh"' in text and 'truth.rain = "chirps"' in text


def test_station_id_can_be_pinned(station_raw):
    r, report = gate(station_raw, "NIM00065134")
    assert r.returncode == 0, r.stderr
    assert "## GHCNh records near the site" not in report.read_text()


@pytest.fixture(scope="module")
def daytime_only(tmp_path_factory):
    c = cfg.load(write_cfg(tmp_path_factory.mktemp("day"), SMALL))
    tru, _ = synth.truth(c, SYNTH_END)
    synth.write_station(c, tru, np.random.default_rng(1), day_only=True)
    return c


def test_station_silent_at_night_fails_and_report_shows_why(daytime_only):
    r, report = gate(daytime_only)
    assert r.returncode == 0, r.stderr
    assert r.stdout.startswith("FAIL.")
    text = report.read_text()
    assert "verdict: FAIL" in text and "Share of days with an observation at each UTC hour" in text


def test_exits_with_a_message_when_no_record_matches(tmp_path):
    c = cfg.load(write_cfg(tmp_path, SMALL))
    d = c.paths.raw / "station"
    d.mkdir(parents=True)
    (d / "ghcnh-station-list.txt").write_text("USW00003812  35.4317  -82.5378  645.6 NC ASHEVILLE AP 72315\n")
    r, _ = gate(c)
    assert r.returncode != 0 and "No GHCNh record" in r.stderr
