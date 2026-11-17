import numpy as np
import pandas as pd
import pytest
from conftest import DEFAULT

from gnostiq import cfg, physics

SITE = cfg.load(DEFAULT).site


def test_es_and_rh():
    assert physics.es(0.0) == pytest.approx(6.112)
    assert physics.rh(20.0, 20.0) == pytest.approx(100.0)
    assert physics.rh(30.0, 10.0) < 30


def test_lapse_bounds_and_fallback():
    assert physics.lapse(np.array([20.0]), np.array([10.5]))[0] == pytest.approx(0.0058, abs=1e-4)
    assert physics.lapse(np.array([20.0]), np.array([19.0]))[0] == 0.003
    assert physics.lapse(np.array([20.0]), np.array([-5.0]))[0] == 0.0098
    assert physics.lapse(np.array([np.nan]), np.array([10.0]))[0] == physics.G_STD


def test_height_recovers_known_terrain():
    t, z = 22.0, 1295.0
    sp = 1013.0 * np.exp(-z / (physics.RD_G * (t + 273.15 + physics.G_STD * z / 2)))
    assert physics.height(sp, 1013.0, t) == pytest.approx(z, abs=5)


def test_cos_zenith_peaks_at_local_noon():
    t = pd.date_range("2025-03-20", periods=144, freq="10min")
    cz = physics.cos_zenith(t, SITE.lat, SITE.lon)
    # solar noon at 8.9 E in late March
    assert t[np.argmax(cz)] == pd.Timestamp("2025-03-20 11:30")
    assert cz.max() > 0.97 and cz.min() < -0.9


def frame(n=72, **cols):
    base = {"valid": pd.date_range("2025-07-01", periods=n, freq="h"), "lead_day": 1, "f_t2m": 24.0, "f_td2m": 20.0,
            "f_tp": 0.0, "f_msl": 1012.0, "f_sp": 900.0, "f_wspd": 3.0, "f_wdir": 45.0}  # fmt: skip
    return pd.DataFrame({**base, **cols})


def test_prior_cools_when_model_terrain_is_lower():
    h = physics.hourly_features(frame(), SITE, z_model=1000.0)
    assert (h.t_prior < h.f_t2m).all()
    assert h.t_prior.iloc[0] == pytest.approx(24.0 - 0.0065 * 295, abs=0.01)
    assert (h.td_prior <= h.t_prior).all() and (h.dep_prior >= 0).all()
    assert (h.sp_prior < h.f_sp).all()


def test_north_easterly_flow_is_positive():
    h = physics.hourly_features(frame(), SITE, 1295.0)
    assert h["ne"].iloc[0] == pytest.approx(3.0)
    assert physics.hourly_features(frame(f_wdir=225.0), SITE, 1295.0)["ne"].iloc[0] == pytest.approx(-3.0)


def test_rain_hour_belongs_to_the_day_it_fell_in():
    # rain stamped 00:00 fell on the previous day
    f = frame()
    f.loc[f.valid == pd.Timestamp("2025-07-02 00:00"), "f_tp"] = 5.0
    h = physics.hourly_features(f, SITE, 1295.0)
    d = physics.daily_features(h, 0).set_index("day").f_tp24
    assert d[pd.Timestamp("2025-07-01")] == 5.0 and d[pd.Timestamp("2025-07-02")] == 0.0
    s = physics.rain_sum(f, 0).set_index("day").f_tp24
    assert s[pd.Timestamp("2025-07-01")] == 5.0


def test_incomplete_days_are_dropped():
    h = physics.hourly_features(frame(n=40), SITE, 1295.0)
    assert len(physics.daily_features(h, 0)) == 1
    assert len(physics.daily_features(h, 6)) == 1


def test_height_matches_the_elevation_open_meteo_reports():
    # from a live response; the cell sits at 1182 m
    z = physics.height(
        np.array([884.9, 884.5, 884.0]), np.array([1012.0, 1011.8, 1011.4]), np.array([23.9, 23.4, 22.9])
    )
    assert np.median(z) == pytest.approx(1182.0, abs=10)


def test_precipitable_water_from_dewpoint_is_plausible():
    assert physics.pw_from_td(22.0, 1013.25) == pytest.approx(43.0, abs=3)
    assert physics.pw_from_td(22.0, 870.0) < physics.pw_from_td(22.0, 1013.25)
    assert physics.pw_from_td(0.0, 870.0) < physics.pw_from_td(22.0, 870.0)


def test_prior_uses_standard_lapse_when_levels_are_missing():
    h = physics.hourly_features(frame(), SITE, z_model=1182.0)
    assert h.t_prior.iloc[0] == pytest.approx(24.0 - 0.0065 * (SITE.elev - 1182.0), abs=1e-6)
    assert (h["gamma"] == 6.5).all()


def test_daily_moisture_supply_falls_back_to_dewpoint():
    h = physics.hourly_features(frame(), SITE, 1295.0)
    d = physics.daily_features(h, 0)
    assert d.tcwv_max.isna().all() and (d.pw > 5).all()
    with_tcwv = physics.daily_features(physics.hourly_features(frame(f_tcwv=40.0), SITE, 1295.0), 0)
    assert (with_tcwv.pw == 40.0).all()


def test_features_cover_every_declared_name():
    h = physics.hourly_features(frame(), SITE, 1295.0)
    assert set(physics.HOURLY_FEATS) <= set(h.columns)
    assert set(physics.DAILY_FEATS) - {"lead_day"} <= set(physics.daily_features(h, 0).columns) | {"lead_day"}
