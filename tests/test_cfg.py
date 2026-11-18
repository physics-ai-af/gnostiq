import pytest
from conftest import DEFAULT, LIVE, NEARBY, write_cfg, write_nearby

from gnostiq import cfg


def test_default_loads():
    c = cfg.load(DEFAULT)
    assert c.site.wmo == "65134"
    assert c.paths.data == DEFAULT.parent / "data"
    assert c.truth.rain_h0 == 0


def test_the_repo_configs_are_valid():
    sites = cfg.sites(cfg.load(LIVE))
    assert len({x.site.name for x in sites}) == len(sites)


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
        ('name = "jos"', 'name = "Jos Plateau"', "site.name"),
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


def test_a_borrowing_site_takes_everything_but_site_and_paths_from_its_donor(tmp_path):
    donor = cfg.load(write_cfg(tmp_path))
    c = cfg.load(write_nearby(tmp_path))
    assert c.donor == "jos" and c.site.name == "nearby" and c.site.elev == 1400.0
    assert c.paths.models == donor.paths.models and c.paths.reports == tmp_path / "nearby" / "reports"
    assert (c.window, c.truth, c.nwp, c.lead_days, c.model) == (donor.window, donor.truth, donor.nwp, donor.lead_days,
                                                                donor.model)  # fmt: skip
    assert donor.donor == "" and donor.paths.models == tmp_path / "data" / "models"


@pytest.mark.parametrize(
    "edit, msg",
    [
        ({"[paths]": "[window]\nstart = 2021-01-01\n\n[paths]"}, "set only"),
        ({'from = "gnostiq.toml"': 'from = "gnostiq.toml"\nseeds = 1'}, "model.seeds"),
        ({'data = "nearby"': 'data = "data"'}, "data directory"),
        ({'name = "nearby"': 'name = "jos"'}, "same site name"),
        ({"lat = 9.64": "lat = 12.0"}, "outside bbox"),
    ],
)
def test_a_borrowing_site_is_checked(tmp_path, edit, msg):
    write_cfg(tmp_path)
    text = NEARBY
    for old, new in edit.items():
        text = text.replace(old, new)
    with pytest.raises(ValueError, match=msg):
        cfg.load(write_nearby(tmp_path, text))


def test_borrowing_does_not_chain(tmp_path):
    write_cfg(tmp_path)
    write_nearby(tmp_path)
    p = tmp_path / "gnostiq-third.toml"
    p.write_text(NEARBY.replace('"nearby"', '"third"').replace("gnostiq.toml", "gnostiq-nearby.toml"))
    with pytest.raises(ValueError, match="borrows its networks too"):
        cfg.load(p)


def test_sites_are_found_beside_the_config(tmp_path):
    c = cfg.load(write_cfg(tmp_path))
    assert [x.site.name for x in cfg.sites(c)] == ["jos"]
    near = cfg.load(write_nearby(tmp_path))
    assert [x.site.name for x in cfg.sites(c)] == ["jos", "nearby"]
    assert [x.site.name for x in cfg.sites(near)] == ["nearby", "jos"]
    (tmp_path / "gnostiq-copy.toml").write_text(NEARBY.replace('data = "nearby"', 'data = "copy"'))
    with pytest.raises(ValueError, match="more than one config .* for nearby"):
        cfg.sites(c)
