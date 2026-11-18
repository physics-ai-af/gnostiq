from dataclasses import replace

import pandas as pd
import pytest

from gnostiq import align, physics


def test_split_labels_follow_the_windows(raw):
    c = raw
    days = [
        "2023-12-31",
        "2024-01-01",
        "2024-12-31 23:00",
        "2025-01-01",
        "2025-04-01",
        "2025-06-30 21:00",
        "2025-07-01",
    ]
    days = pd.to_datetime(days, format="ISO8601")
    assert list(align.split(c, days)) == ["other", "train", "train", "other", "test", "test", "other"]


def test_pairs_keep_train_and_test_apart(pairs):
    c = pairs
    p = pd.read_parquet(c.paths.processed / "pairs_hourly.parquet")
    assert p[p.split == "train"].valid.max() < pd.Timestamp(c.window.test_start)
    assert p[p.split == "test"].valid.min() >= pd.Timestamp(c.window.test_start)
    assert set(p.lead_day) == set(c.lead_days)
    assert {"o_t2m", "o_td2m", "t_prior", "td_prior", "dep_prior", "src"} <= set(p.columns)
    assert not p.duplicated(["valid", "lead_day"]).any() and p.o_t2m.notna().all()


def test_hourly_pairs_join_on_valid_time(pairs):
    c = pairs
    p = pd.read_parquet(c.paths.processed / "pairs_hourly.parquet")
    obs = pd.read_parquet(c.paths.interim / "obs.parquet").set_index("valid").t
    nwp = pd.read_parquet(c.paths.interim / f"nwp_{c.nwp.base}.parquet").set_index(["valid", "lead_day"]).f_t2m
    row = p.iloc[len(p) // 2]
    assert row.o_t2m == obs[row.valid] and row.f_t2m == nwp[(row.valid, row.lead_day)]
    m = c.nwp.extra[0]
    extra = pd.read_parquet(c.paths.interim / f"nwp_{m}.parquet").set_index(["valid", "lead_day"]).f_t2m
    assert row[f"x_{m}_dt2m"] == pytest.approx(extra[(row.valid, row.lead_day)] - row.f_t2m)


def test_daily_pairs_carry_truth_and_a_moisture_supply(pairs):
    c = pairs
    d = pd.read_parquet(c.paths.processed / "pairs_daily.parquet")
    assert set(physics.DAILY_FEATS) <= set(d.columns)
    assert d.o_tp24.notna().all() and (d.o_tp24 >= 0).all() and (d.pw >= 5).all()
    truth = align.truth_rain(c).set_index("day").tp24
    row = d.iloc[len(d) // 2]
    assert row.o_tp24 == truth[row.day]
    hourly = pd.read_parquet(c.paths.interim / f"nwp_{c.nwp.base}.parquet")
    h = hourly[
        (hourly.lead_day == row.lead_day) & (hourly.valid > row.day) & (hourly.valid <= row.day + pd.Timedelta(days=1))
    ]
    assert row.f_tp24 == pytest.approx(h.f_tp.sum())


def test_truth_rain_follows_the_configured_source(pairs):
    c = pairs
    chirps = align.truth_rain(c)
    assert list(chirps.columns) == ["day", "tp24"] and len(chirps) > 300
    gauge = replace(c, truth=replace(c.truth, rain="station"))
    # the synthetic station has no gauge
    assert list(align.truth_rain(gauge).columns) == ["day", "tp24"]
    assert gauge.truth.rain_h0 == 6 and c.truth.rain_h0 == 0


def test_truth_rain_names_the_missing_step(raw, tmp_path):
    from gnostiq.cfg import Paths

    empty = replace(raw, paths=Paths(tmp_path))
    with pytest.raises(FileNotFoundError, match="pull --only precip"):
        align.truth_rain(empty)
    with pytest.raises(FileNotFoundError, match="gnostiq build"):
        align.truth_rain(replace(empty, truth=replace(empty.truth, rain="station")))
