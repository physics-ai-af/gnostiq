import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
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
    assert '[site]\nghcnh = "NIM00065134"\n\n[truth]\ntemp = "ghcnh"\nrain = "chirps"\n```' in text
    assert "from the configured site" not in text


def test_suggests_moving_the_site_onto_the_station(tmp_path):
    c = cfg.load(write_cfg(tmp_path, SMALL))
    tru, _ = synth.truth(c, SYNTH_END)
    synth.write_station(c, tru, np.random.default_rng(1))
    c = cfg.load(write_cfg(tmp_path, {**SMALL, "lat = 9.8667": "lat = 10.0667"}))
    r, report = gate(c)
    assert r.returncode == 0, r.stderr
    text = report.read_text()
    assert "NIM00065134 puts the station at 9.8667, 8.9000, 1295 m, 22 km from the configured site." in text
    assert '[site]\nghcnh = "NIM00065134"\nlat = 9.8667\nlon = 8.9\nelev_m = 1295\n' in text


def test_station_id_can_be_pinned(station_raw):
    r, report = gate(station_raw, "NIM00065134")
    assert r.returncode == 0, r.stderr
    assert "## GHCNh records near the site" not in report.read_text()


def test_a_rough_synop_position_does_not_move_the_site(tmp_path):
    c = cfg.load(write_cfg(tmp_path, SMALL))
    tru, _ = synth.truth(c, SYNTH_END)
    synth.write_station(c, tru, np.random.default_rng(1))
    path = c.paths.raw / "station" / "GHCNh_NIM00065134_por.psv"
    g = pd.read_csv(path, sep="|", dtype=str, keep_default_na=False)
    # the thermometer the METAR reads, filed with a grid-box position as at Abuja
    t = tru.set_index(tru.valid.dt.strftime("%Y-%m-%dT%H:%M:%S")).t.round()
    g["temperature"] = g.DATE.map(t).astype(str)
    g["LATITUDE"], g["LONGITUDE"] = "9.75", "9.0"
    g.to_csv(path, sep="|", index=False)
    r, report = gate(c)
    assert r.returncode == 0, r.stderr
    text = report.read_text()
    assert "- reading: same instrument" in text and "puts the station at" not in text
    assert '[site]\nghcnh = "NIM00065134"\n\n[truth]' in text


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
