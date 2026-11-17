import json

import numpy as np
import pandas as pd
import pytest
from conftest import write_cfg
from rasterio.errors import RasterioIOError

from gnostiq import cfg
from gnostiq.ingest import static


@pytest.mark.parametrize(
    "lat, lon, tile",
    [
        (9.87, 8.90, "Copernicus_DSM_COG_10_N09_00_E008_00_DEM"),
        (-1.30, 36.80, "Copernicus_DSM_COG_10_S02_00_E036_00_DEM"),
        (14.70, -17.40, "Copernicus_DSM_COG_10_N14_00_W018_00_DEM"),
    ],
)
def test_dem_tile_is_named_by_its_south_west_corner(lat, lon, tile):
    assert static.dem_url(lat, lon) == f"/vsicurl/https://copernicus-dem-30m.s3.amazonaws.com/{tile}/{tile}.tif"


def frame():
    # from a live response; the cell sits at 1182 m
    return pd.DataFrame({"f_sp": [884.9, 884.5, 884.0], "f_msl": [1012.0, 1011.8, 1011.4], "f_t2m": [23.9, 23.4, 22.9]})


def test_model_height_comes_from_the_models_own_pressures(tmp_path, monkeypatch):
    c = cfg.load(write_cfg(tmp_path))
    monkeypatch.setattr(static.nwp, "live", lambda c, days=3: (frame(), 1182.0))
    hyps, api = static.model_height(c)
    assert hyps == pytest.approx(1182.0, abs=10) and api == 1182.0


def test_model_height_ignores_a_missing_api_elevation(tmp_path, monkeypatch):
    c = cfg.load(write_cfg(tmp_path))
    monkeypatch.setattr(static.nwp, "live", lambda c, days=3: (frame(), float("nan")))
    assert static.model_height(c)[1] is None


def test_pull_writes_once_and_survives_a_dem_outage(tmp_path, monkeypatch):
    c = cfg.load(write_cfg(tmp_path))
    calls = []

    def height(c):
        calls.append(1)
        return 1180.0, 1182.0

    def no_dem(lat, lon):
        raise RasterioIOError("HTTP 503")

    monkeypatch.setattr(static, "model_height", height)
    monkeypatch.setattr(static, "dem", no_dem)
    out = static.pull(c)
    assert out["z_model_hyps"] == 1180.0 and out["z_station"] == c.site.elev and "z_dem_point" not in out
    assert json.loads((c.paths.processed / "static.json").read_text()) == out
    static.pull(c)
    assert len(calls) == 1

    monkeypatch.setattr(static, "dem", lambda lat, lon: (1290.0, 1240.0))
    assert static.pull(c, refresh=True)["z_dem_9km"] == 1240.0 and len(calls) == 2


def test_z_model_prefers_pressure_estimate_then_api_then_station(tmp_path):
    c = cfg.load(write_cfg(tmp_path))
    path = c.paths.processed / "static.json"
    assert static.z_model(c) == c.site.elev
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"z_model_hyps": None, "z_model_api": 1182.0}))
    assert static.z_model(c) == 1182.0
    path.write_text(json.dumps({"z_model_hyps": 1175.5, "z_model_api": 1182.0}))
    assert static.z_model(c) == 1175.5
    assert not np.isnan(static.z_model(c))
