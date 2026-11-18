import pytest
from conftest import DEFAULT, LIVE, write_cfg

from gnostiq import cfg


def test_default_loads():
    c = cfg.load(DEFAULT)
    assert c.site.wmo == "65134"
    assert c.paths.data == DEFAULT.parent / "data"
    assert c.truth.rain_h0 == 0


def test_the_repo_config_is_valid():
    cfg.load(LIVE)


@pytest.mark.parametrize(
    "old, new, msg",
    [
        ("lat = 9.8667", "lat = 12.0", "outside bbox"),
        ("bbox = [9.4, 10.1,", "bbox = [10.1, 9.4,", "not ordered"),
        ("bbox = [9.4, 10.1, 8.6, 9.2]", "bbox = [9.4, 10.1]", "4 values"),
        ("elev_m = 1295.0", "elev_m = -40.0", "elev_m"),
        ('tz = "Africa/Lagos"', 'tz = "Africa/Jos"', "tz unknown"),
        ("train_end = 2026-03-31", "train_end = 2026-05-01", "start < train_end"),
        ("test_end = 2026-10-31", 'test_end = "2026-10-31"', "bare TOML dates"),
        ("wet_months = [4,", "wet_months = [13,", "wet_months"),
        ("lead_days = [1, 2, 3, 4, 5, 6, 7]", "lead_days = [1, 10]", "lead_days"),
        ("lead_days = [1, 2, 3, 4, 5, 6, 7]", "lead_days = [3, 1]", "lead_days"),
        ('temp = "merged"', 'temp = "era5"', "truth.temp"),
        ('rain = "chirps"', 'rain = "imerg"', "truth.rain"),
        ('extra = ["gfs_seamless", "icon_seamless"]', 'extra = ["ecmwf_ifs025"]', "nwp.base"),
        ("start = 2024-01-01", "start = 2019-01-01", "nwp.start"),
        ("heavy_mm = 10.0", "heavy_mm = 0.5", "thresholds"),
        ("seeds = 3", "seeds = 0", "model settings"),
        ('icao = "DNJO"\n', "", "missing site.icao"),
    ],
)
def test_rejects(tmp_path, old, new, msg):
    with pytest.raises(ValueError, match=msg):
        cfg.load(write_cfg(tmp_path, {old: new}))


def test_all_errors_reported_together(tmp_path):
    with pytest.raises(ValueError) as e:
        cfg.load(write_cfg(tmp_path, {"lat = 9.8667": "lat = 12.0", 'tz = "Africa/Lagos"': 'tz = "Nowhere"'}))
    assert "outside bbox" in str(e.value) and "tz unknown" in str(e.value)


def test_station_rain_day_starts_at_06(tmp_path):
    assert cfg.load(write_cfg(tmp_path, {'rain = "chirps"': 'rain = "station"'})).truth.rain_h0 == 6


def test_find_walks_up(tmp_path, monkeypatch):
    p = write_cfg(tmp_path)
    sub = tmp_path / "a" / "b"
    sub.mkdir(parents=True)
    monkeypatch.delenv("GNOSTIQ_CFG", raising=False)
    monkeypatch.chdir(sub)
    assert cfg.find() == p.resolve()


def test_env_override(tmp_path, monkeypatch):
    p = write_cfg(tmp_path, {'name = "jos"': 'name = "jos-alt"'})
    monkeypatch.setenv("GNOSTIQ_CFG", str(p))
    cfg.get.cache_clear()
    try:
        assert cfg.get().site.name == "jos-alt"
    finally:
        cfg.get.cache_clear()
