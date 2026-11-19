import numpy as np
import pandas as pd
import pytest
from conftest import write_cfg
from scipy.io import netcdf_file

from gnostiq import cfg
from gnostiq.ingest import tamsat
from gnostiq.io import Missing


def write_nc(path, lat0, lon0, value, gap=False):
    # the published layout: rfe and rfe_filled on a 0.0375 degree grid, latitude ascending
    lat = np.round(np.arange(lat0 - 0.3, lat0 + 0.3, 0.0375), 4)
    lon = np.round(np.arange(lon0 - 0.3, lon0 + 0.3, 0.0375), 4)
    f = netcdf_file(path, "w")
    f.createDimension("time", 1)
    f.createDimension("lat", len(lat))
    f.createDimension("lon", len(lon))
    for name, vals, units in (("lat", lat, "degrees_north"), ("lon", lon, "degrees_east")):
        v = f.createVariable(name, "f8", (name,))
        v[:] = vals
        v.units = units
    a = np.full((1, len(lat), len(lon)), value, "f4")
    if gap:
        i, j = np.abs(lat - lat0).argmin(), np.abs(lon - lon0).argmin()
        a[0, i + 1, j + 1] = -99
    for name, add in (("rfe", 0), ("rfe_filled", 500)):
        v = f.createVariable(name, "f4", ("time", "lat", "lon"))
        v[:] = a + add if add else a
        v.units = "mm"
        v._FillValue = np.float32(-99)
    f.close()


def test_the_unfilled_estimate_is_read_and_gaps_skipped(tmp_path):
    p = tmp_path / "rfe.nc"
    write_nc(p, 9.0, 7.26, 12.5, gap=True)
    pt, box = tamsat.read(p, 9.0, 7.26)
    assert pt == pytest.approx(12.5) and box == pytest.approx(12.5)


def test_file_names_follow_the_archive():
    assert tamsat.url(pd.Timestamp("2025-07-01")).endswith("/daily/2025/07/rfe2025_07_01.v3.1.nc")


def test_pull_reads_only_the_scored_days_and_keeps_no_files(tmp_path, monkeypatch):
    c = cfg.load(write_cfg(tmp_path, {"train_end = 2026-03-31": "train_end = 2025-03-31",
                                      "test_start = 2026-04-01": "test_start = 2025-04-01",
                                      "test_end = 2026-10-31": "test_end = 2025-04-10"}))  # fmt: skip
    asked = []

    def fetch(url, path, **kw):
        day = pd.Timestamp(url.rsplit("rfe", 1)[1][:10].replace("_", "-"))
        asked.append(day)
        if day == pd.Timestamp("2025-04-05"):
            raise Missing("404")
        write_nc(path, c.site.lat, c.site.lon, float(day.day))
        return path

    monkeypatch.setattr(tamsat, "fetch", fetch)
    monkeypatch.setattr(tamsat.time, "sleep", lambda s: None)
    out = tamsat.pull(c)
    assert asked == list(pd.date_range("2025-04-01", "2025-04-10"))
    assert out.day.dt.day.tolist() == [1, 2, 3, 4, 6, 7, 8, 9, 10] and out.tp24.tolist() == out.day.dt.day.tolist()
    assert not list(tamsat.cache(c).parent.glob("*.nc"))
    asked.clear()
    tamsat.pull(c)
    assert asked == [pd.Timestamp("2025-04-05")]
