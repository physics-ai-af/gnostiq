import numpy as np
import pandas as pd

from gnostiq import qc


def series(values, freq="3h", start="2025-07-01"):
    return pd.Series(values, index=pd.date_range(start, periods=len(values), freq=freq), dtype=float)


def test_spike_is_one_reading_far_from_both_neighbours():
    x = series([20, 20.5, 33, 21, 20, 20, 8, 20])
    assert list(qc.spikes(x)) == [x.index[2], x.index[6]]


def test_a_front_is_not_a_spike():
    # a jump that persists is weather
    assert len(qc.spikes(series([28, 28, 17, 17, 16.5]))) == 0
    assert len(qc.spikes(series([20, 33, 20], freq="12h"))) == 0


def test_spike_check_skips_gaps():
    x = series([20, np.nan, 33, np.nan, 20])
    assert len(qc.spikes(x)) == 0


def test_flatline_needs_many_identical_readings_over_a_day():
    stuck = series([21.0] * 12 + [22.0, 23.0])
    assert len(qc.flatlines(stuck)) == 12
    # calm-night METAR repeats must survive
    assert len(qc.flatlines(series([21.0] * 14, freq="h"))) == 0
    assert len(qc.flatlines(series([21.0] * 5 + [22.0] * 5))) == 0


def test_outlier_is_judged_against_the_same_month_and_hour():
    idx = pd.date_range("2025-07-01 12:00", periods=30, freq="D")
    x = pd.Series(25 + np.sin(np.arange(30)), index=idx)
    x.iloc[10] = 41.0
    assert list(qc.outliers(x)) == [idx[10]]
    assert len(qc.outliers(x.iloc[:8].where(x.index[:8] != idx[3], 41.0))) == 0


def test_run_removes_the_planted_error_and_reports_it(built):
    c = built
    out = qc.run(c)
    raw = pd.read_parquet(c.paths.interim / "station.parquet")
    assert raw.t.max() == 61.0 and out.t.max() < 45
    assert out.t.notna().all() and (out.td.dropna() <= out.loc[out.td.notna(), "t"]).all()
    assert list(out.columns) == ["valid", "t", "td", "src"]
    report = (c.paths.reports / "qc.md").read_text()
    assert "| t range | 1 |" in report and "Source mix" in report
    pd.testing.assert_frame_equal(out, pd.read_parquet(c.paths.interim / "obs.parquet"))


def test_run_handles_dewpoint_above_temperature(built, tmp_path):
    from dataclasses import replace

    from gnostiq.cfg import Paths

    c = replace(built, paths=Paths(tmp_path))
    c.paths.ensure()
    idx = pd.date_range("2025-07-01", periods=6, freq="3h")
    o = pd.DataFrame(
        {"valid": idx, "t": [20.0, 20.0, 20.0, 20.0, np.nan, 20.0], "td": [18.0, 20.3, 22.0, np.nan, 15.0, 19.0]}
    )
    o["src"] = "ghcnh"
    o.to_parquet(c.paths.interim / "station.parquet", index=False)
    out = qc.run(c).set_index("valid")
    assert out.td[idx[1]] == 20.0  # rounding: clipped to temperature
    assert np.isnan(out.td[idx[2]])  # 2 degC over: a bad report
    assert idx[4] not in out.index  # dewpoint with no temperature to check it against
    assert len(out) == 5
