import numpy as np
import pytest

from gnostiq import dist


def test_crps_norm_matches_sampling():
    rng = np.random.default_rng(0)
    x = rng.normal(1.0, 2.0, 200_000)
    est = np.abs(x - 0.3).mean() - 0.5 * np.abs(x[:100_000] - x[100_000:]).mean()
    assert dist.crps_norm(0.3, 1.0, 2.0) == pytest.approx(est, abs=0.02)


def test_crps_norm_point_forecast_is_absolute_error():
    assert dist.crps_norm([1.0, 2.0], [3.0, 2.5], [0.0, np.nan]).tolist() == [2.0, 0.5]


def test_crps_quantiles_point_forecast_is_absolute_error():
    q = np.full((2, 99), 4.0)
    assert dist.crps_quantiles(np.array([1.0, 6.0]), q) == pytest.approx([3.0, 2.0])


def test_hurdle_quantiles():
    q = dist.hurdle_quantiles([0.3, 1.0], [8.0, 8.0], [1.2, 1.2], 1.0)
    assert (np.diff(q, axis=1) >= 0).all() and (q >= 0).all()
    assert (q[0, :69] == 0).all() and q[0, 71] > 1.0
    assert (q[1] > 1.0).all()


def test_hurdle_exceed():
    p = np.array([0.4])
    assert dist.hurdle_exceed(p, [8.0], [1.0], 1.0, 1.0)[0] == pytest.approx(0.4)
    assert dist.hurdle_exceed(p, [8.0], [1.0], 1.0, 9.0)[0] == pytest.approx(0.4 * np.exp(-1))
