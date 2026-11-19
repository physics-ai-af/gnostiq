import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent))

import synth  # noqa: E402

from gnostiq import cfg  # noqa: E402

# a frozen copy: the live config changes with the site, and fixtures edit this one by string
DEFAULT = Path(__file__).resolve().parent / "data" / cfg.FILENAME
LIVE = Path(__file__).resolve().parents[1] / cfg.FILENAME

SMALL = {
    "start = 2021-01-01": "start = 2023-07-01",
    "train_end = 2026-03-31": "train_end = 2024-12-31",
    "test_start = 2026-04-01": "test_start = 2025-04-01",
    "test_end = 2026-10-31": "test_end = 2025-06-30",
    'extra = ["gfs_seamless", "icon_seamless"]': 'extra = ["gfs_seamless"]\ncompare = ["jma_gsm"]',
    "lead_days = [1, 2, 3, 4, 5, 6, 7]": "lead_days = [1, 3]",
    "seeds = 3": "seeds = 1",
    "hidden = 64": "hidden = 16",
    "max_epochs = 300": "max_epochs = 6",
    "patience = 25": "patience = 3",
}
SYNTH_END = "2025-07-05"


def write_cfg(tmp_path, edits=None):
    text = DEFAULT.read_text()
    for old, new in (edits or {}).items():
        assert old in text, f"fixture drift: {old!r} not in {cfg.FILENAME}"
        text = text.replace(old, new)
    p = tmp_path / cfg.FILENAME
    p.write_text(text)
    return p


NEARBY = """[site]
name = "nearby"
wmo = "65000"
icao = "DNXX"
lat = 9.64
lon = 8.87
elev_m = 1400.0
tz = "Africa/Lagos"
bbox = [9.4, 10.1, 8.6, 9.2]

[model]
from = "gnostiq.toml"

[paths]
data = "nearby"
"""


def write_nearby(tmp_path, text=NEARBY):
    # a second site on the first site's networks
    p = tmp_path / "gnostiq-nearby.toml"
    p.write_text(text)
    return p


@pytest.fixture(scope="session")
def station_raw(tmp_path_factory):
    c = cfg.load(write_cfg(tmp_path_factory.mktemp("station"), SMALL))
    tru, _ = synth.truth(c, SYNTH_END)
    synth.write_station(c, tru, np.random.default_rng(1))
    return c


@pytest.fixture(scope="session")
def nwp_raw(tmp_path_factory):
    c = cfg.load(write_cfg(tmp_path_factory.mktemp("nwp"), SMALL))
    tru, daily = synth.truth(c, SYNTH_END)
    synth.write_nwp(c, tru, daily, np.random.default_rng(2), bare=True)
    return c


@pytest.fixture(scope="session")
def raw(tmp_path_factory):
    c = cfg.load(write_cfg(tmp_path_factory.mktemp("run"), SMALL))
    synth.make(c, SYNTH_END, bare=True)
    return c


@pytest.fixture(scope="session")
def built(raw):
    from gnostiq.ingest import nwp, station

    station.build(raw)
    nwp.build(raw)
    return raw


@pytest.fixture(scope="session")
def pairs(built):
    from gnostiq import align, qc

    qc.run(built)
    align.build(built)
    return built


@pytest.fixture(scope="session")
def based(pairs):
    from gnostiq import baselines

    baselines.run(pairs)
    return pairs


@pytest.fixture(scope="session")
def trained(based):
    from gnostiq import train

    train.run(based)
    return based
