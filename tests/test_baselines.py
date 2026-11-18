import numpy as np
import pandas as pd
import pytest
from scipy import special

from gnostiq import align, baselines, dist


def test_climatology_recovers_a_diurnal_and_annual_cycle(raw):
    c = raw
    t = pd.date_range("2023-07-01", "2024-12-31 21:00", freq="3h")
    hour = 2 * np.pi * ((t.hour + c.site.lon / 15) % 24) / 24
    signal = 22 + 4 * np.sin(hour) + 3 * np.cos(2 * np.pi * t.day_of_year / 365.25)
    obs = pd.DataFrame({"valid": t, "o": signal + np.random.default_rng(0).normal(0, 0.5, len(t))})
    mu, sigma = baselines.clim_hourly(c, obs, "o", t[:400])
    assert np.abs(mu - signal[:400]).max() < 0.3
    assert sigma == pytest.approx(0.5, abs=0.1)


def test_climatology_ignores_the_test_window(raw):
    c = raw
    t = pd.date_range("2024-01-01", "2025-06-30 21:00", freq="3h")
    obs = pd.DataFrame({"valid": t, "o": np.where(t >= pd.Timestamp(c.window.test_start), 99.0, 20.0)})
    mu, _ = baselines.clim_hourly(c, obs, "o", t[-50:])
    assert np.abs(mu - 20.0).max() < 1e-6


def test_emos_removes_a_bias_and_learns_the_spread():
    rng = np.random.default_rng(0)
    t = pd.date_range("2024-01-01", periods=3000, freq="3h")
    prior = 22 + 5 * np.sin(np.arange(3000) / 8)
    y = prior - 2.0 + rng.normal(0, 1.5, 3000)
    x, z = baselines.emos_design(pd.DataFrame({"valid": t, "p": prior}), "p", 8.9)
    th = baselines.emos_fit(x, z, y)
    mu, sigma = x @ th[: x.shape[1]], np.exp(z @ th[x.shape[1] :])
    assert np.mean(mu - prior) == pytest.approx(-2.0, abs=0.1)
    assert np.mean(sigma) == pytest.approx(1.5, abs=0.15)


def test_multi_model_emos_learns_to_lean_on_a_better_model(raw):
    c = raw
    rng = np.random.default_rng(1)
    n = 4000
    t = pd.date_range("2024-01-01", periods=n, freq="3h")
    truth = 22 + 5 * np.sin(np.arange(n) / 8) + rng.normal(0, 1.0, n)
    prior = truth + rng.normal(0, 1.5, n)
    better = truth + rng.normal(0, 0.5, n)
    df = pd.DataFrame({"valid": t, "lead_day": 1, "t_prior": prior, "o_t2m": truth, "x_icon_dt2m": better - prior})
    df.loc[::10, "x_icon_dt2m"] = np.nan
    fit, test = df.iloc[:3000], df.iloc[3000:].reset_index(drop=True)
    one = baselines.emos(c, fit, test, "t_prior", "o_t2m")
    two = baselines.emos(c, fit, test, "t_prior", "o_t2m", ["x_icon_dt2m"])
    err = [np.mean(np.abs(m[0] - test.o_t2m)) for m in (one, two)]
    assert err[1] < 0.6 * err[0] and np.isfinite(two[0][test.lead_day == 1]).all()


def test_rain_emos_ties_probability_and_amount_to_the_forecast():
    rng = np.random.default_rng(0)
    n = 4000
    f = rng.gamma(0.6, 8, n)
    wet = rng.random(n) < special.expit(-1.5 + 0.9 * np.sqrt(f))
    y = np.where(wet, 1 + rng.gamma(1.2, 2 + 0.8 * f), 0.0)
    p = pd.DataFrame({"f_tp24_sqrt": np.sqrt(f), "doy_s": 0.0, "doy_c": 1.0})
    b, th = baselines.rain_emos_fit(baselines.rain_design(p), y, 1.0)
    grid = pd.DataFrame({"f_tp24_sqrt": np.sqrt([0.0, 5.0, 40.0]), "doy_s": 0.0, "doy_c": 1.0})
    prob, mean, shape = baselines.rain_emos_predict(baselines.rain_design(grid), b, th)
    assert prob[0] < prob[1] < prob[2] and mean[0] < mean[1] < mean[2]
    assert prob[0] == pytest.approx(special.expit(-1.5), abs=0.06) and (shape > 0).all()


def test_point_forecast_becomes_a_degenerate_distribution(raw):
    c = raw
    key = pd.DataFrame({"day": pd.date_range("2025-05-01", periods=4), "lead_day": 1, "split": "test", "obs": 0.0})
    f = baselines.point_rain(key, [0.0, 0.4, 3.0, np.nan], c)
    assert len(f) == 3 and f.p1.tolist() == [0.0, 0.0, 1.0] and f.p10.tolist() == [0.0, 0.0, 0.0]
    assert (f[dist.QCOLS].nunique(axis=1) == 1).all() and f.q50.tolist() == [0.0, pytest.approx(0.4), 3.0]


def test_rain_climatology_uses_days_near_the_calendar_date(raw):
    c = raw
    days = pd.date_range("2023-07-01", "2024-12-31")
    truth = pd.DataFrame({"day": days, "tp24": np.where(days.month.isin([6, 7, 8]), 12.0, 0.0)})
    ask = pd.Series(pd.to_datetime(["2025-07-15", "2025-01-15"]))
    p1, p10, q = baselines.clim_daily(c, truth, ask)
    assert p1.tolist() == [1.0, 0.0] and p10.tolist() == [1.0, 0.0] and q[0, 49] == 12.0 and q[1, 98] == 0.0


def test_hourly_baselines_cover_every_system(based):
    c = based
    pred = pd.read_parquet(c.paths.processed / "pred_hourly_base.parquet")
    assert set(pred.system) == {"clim", "persist", "raw", "lapse", "emos", "emos_multi", f"raw:{c.nwp.extra[0]}"}
    assert set(pred["var"]) == {"t2m", "td2m"} and pred.mu.notna().all()
    assert set(pred.system[pred.sigma.notna()]) == {"clim", "emos", "emos_multi"} and (pred.sigma.dropna() > 0).all()


def test_persistence_uses_the_observation_one_lead_back(based):
    c = based
    pred = pd.read_parquet(c.paths.processed / "pred_hourly_base.parquet")
    obs = pd.read_parquet(c.paths.interim / "obs.parquet").set_index("valid").t
    p = pred[(pred.system == "persist") & (pred["var"] == "t2m") & (pred.lead_day == 3)].iloc[100]
    assert p.mu == obs[p.valid - pd.Timedelta(days=3)]


def test_terrain_correction_beats_the_raw_model_on_the_warm_biased_synthetic_run(based):
    c = based
    pred = pd.read_parquet(c.paths.processed / "pred_hourly_base.parquet")
    t = pred[(pred["var"] == "t2m") & (pred.split == "test")]
    mae = (t.mu - t.obs).abs().groupby(t.system).mean()
    assert mae["lapse"] < mae["raw"] and mae["emos"] < mae["lapse"]


def test_daily_baselines_are_coherent(based):
    c = based
    pred = pd.read_parquet(c.paths.processed / "pred_daily_base.parquet")
    assert set(pred.system) == {"clim", "persist", "raw", "emos", f"raw:{c.nwp.extra[0]}"}
    q = pred[dist.QCOLS].to_numpy()
    assert (np.diff(q, axis=1) >= -1e-6).all() and (q >= 0).all()
    assert ((pred.p10 <= pred.p1 + 1e-9) & pred.p1.between(0, 1)).all()


def test_rain_persistence_uses_the_last_complete_day_at_issue_time(based):
    c = based
    pred = pd.read_parquet(c.paths.processed / "pred_daily_base.parquet")
    truth = align.truth_rain(c).set_index("day").tp24
    p = pred[(pred.system == "persist") & (pred.lead_day == 3)].iloc[40]
    assert p.q50 == pytest.approx(truth[p.day - pd.Timedelta(days=4)], abs=1e-4)
