import numpy as np
import pandas as pd
import pytest
import rasterio
from conftest import write_cfg
from rasterio.transform import from_origin

from gnostiq import cfg
from gnostiq.ingest import precip


def test_urls_match_the_chc_layout():
    d = pd.Timestamp("2026-07-04")
    assert precip.url(d, "sat", "final") == (
        "https://data.chc.ucsb.edu/products/CHIRPS/v3.0/daily/final/sat/2026/chirps-v3.0.sat.2026.07.04.tif"
    )
    assert precip.url(d, "rnl", "final").endswith("/final/rnl/2026/chirps-v3.0.rnl.2026.07.04.tif")
    assert precip.url(d, "rnl", "prelim").endswith("/daily/prelim/sat/2026/chirps-v3.0.prelim.2026.07.04.tif")


def tif(path, block, nodata=-9999):
    a = np.zeros((40, 40), dtype="float32")
    a[19:22, 19:22] = block
    with rasterio.open(path, "w", driver="GTiff", height=40, width=40, count=1, dtype="float32", crs="EPSG:4326",
                       transform=from_origin(8.0, 11.0, 0.05, 0.05), nodata=nodata) as ds:  # fmt: skip
        ds.write(a, 1)
    return path


def test_read_cell_returns_pixel_and_block_mean(tmp_path):
    path = tif(tmp_path / "c.tif", [[1, 2, 3], [4, 5, 6], [7, 8, -9999]])
    pt, box = precip.read_cell(path, lat=9.975, lon=9.025)
    assert pt == 5.0 and box == 4.5


def test_read_cell_all_nodata_is_nan(tmp_path):
    path = tif(tmp_path / "c.tif", np.full((3, 3), -9999.0))
    pt, box = precip.read_cell(path, lat=9.975, lon=9.025)
    assert np.isnan(pt) and np.isnan(box)


def test_read_cell_rejects_a_site_on_the_raster_edge(tmp_path):
    path = tif(tmp_path / "c.tif", np.ones((3, 3)))
    with pytest.raises(ValueError, match="raster edge"):
        precip.read_cell(path, lat=10.99, lon=8.01)


@pytest.fixture
def chc(tmp_path, monkeypatch):
    edits = {
        "start = 2021-01-01": "start = 2025-01-01",
        "start = 2024-01-01": "start = 2025-01-01",
        "train_end = 2026-03-31": "train_end = 2025-12-31",
    }
    c = cfg.load(write_cfg(tmp_path, edits))
    state = {"final_until": pd.Timestamp("2100-01-01"), "down": set(), "calls": []}

    def one(day, lat, lon, flavor):
        state["calls"].append(day)
        if day in state["down"]:
            return None
        stage = "final" if day <= state["final_until"] else "prelim"
        return {"day": day, "pt": 1.0, "tp24": 2.0 if stage == "final" else 9.0, "stage": stage}

    monkeypatch.setattr(precip, "one", one)
    monkeypatch.setattr(precip, "PAUSE", 0)
    return c, state


def test_pull_reads_each_day_once(chc):
    c, state = chc
    out = precip.pull(c)
    assert out.day.is_unique and out.day.min() == pd.Timestamp("2025-01-01") and len(out) == len(state["calls"])
    assert precip.cache(c).name == "chirps_sat.parquet" and precip.cache(c).exists()
    state["calls"].clear()
    precip.pull(c)
    assert state["calls"] == []


def test_pull_replaces_preliminary_days_once_final_exists(chc):
    c, state = chc
    state["final_until"] = pd.Timestamp("2025-03-31")
    first = precip.pull(c)
    n_prelim = int((first.stage == "prelim").sum())
    assert n_prelim > 0 and (first.tp24[first.stage == "prelim"] == 9.0).all()

    state["final_until"] = pd.Timestamp("2100-01-01")
    state["calls"].clear()
    second = precip.pull(c)
    assert len(state["calls"]) == n_prelim and (second.stage == "final").all() and (second.tp24 == 2.0).all()


def test_pull_retries_days_the_server_refused(chc):
    c, state = chc
    state["down"] = {pd.Timestamp("2025-02-10"), pd.Timestamp("2025-02-11")}
    first = precip.pull(c)
    assert not first.day.isin(state["down"]).any()
    gone, state["down"] = state["down"], set()
    state["calls"].clear()
    second = precip.pull(c)
    assert set(state["calls"]) == gone and second.day.isin(gone).sum() == 2


def test_pull_reads_the_forecast_years_first(tmp_path, monkeypatch):
    edits = {
        "start = 2021-01-01": "start = 2025-01-01",
        "start = 2024-01-01": "start = 2025-06-01",
        "train_end = 2026-03-31": "train_end = 2025-12-31",
    }
    c = cfg.load(write_cfg(tmp_path, edits))
    calls = []

    def one(day, lat, lon, flavor):
        calls.append(day)
        return {"day": day, "pt": 1.0, "tp24": 1.0, "stage": "final"}

    monkeypatch.setattr(precip, "one", one)
    monkeypatch.setattr(precip, "PAUSE", 0)
    out = precip.pull(c)
    cut = pd.Timestamp("2025-06-01")
    assert calls[0] == cut and calls == sorted(calls, key=lambda d: (d < cut, d))
    assert out.day.is_monotonic_increasing and not list(precip.cache(c).parent.glob("*.part"))


def test_pull_stops_at_the_end_of_the_test_season(chc):
    c, state = chc
    out = precip.pull(c)
    assert out.day.max() == pd.Timestamp(c.window.test_end) and max(state["calls"]) == pd.Timestamp(c.window.test_end)
