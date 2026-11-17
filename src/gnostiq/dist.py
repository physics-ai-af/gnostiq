"""Forecast distributions and scores."""

import numpy as np
from scipy import stats

TAU = np.arange(1, 100) / 100
QCOLS = [f"q{i:02d}" for i in range(1, 100)]
Z80 = 1.2815515655


def crps_norm(y, mu, sigma):
    # falls back to absolute error where sigma is missing or zero
    y, mu, sigma = (np.asarray(a, float) for a in (y, mu, sigma))
    ok = sigma > 0
    s = np.where(ok, sigma, 1.0)
    z = (y - mu) / s
    val = s * (z * (2 * stats.norm.cdf(z) - 1) + 2 * stats.norm.pdf(z) - 1 / np.sqrt(np.pi))
    return np.where(ok, val, np.abs(y - mu))


def crps_quantiles(y, q):
    d = np.asarray(y, float)[:, None] - q
    return 2 * np.where(d >= 0, TAU * d, (TAU - 1) * d).mean(axis=1)


def hurdle_quantiles(p, m, k, wet):
    # zero w.p. 1-p, else wet + Gamma(k, mean m)
    p, m, k = (np.asarray(a, float)[:, None] for a in (p, m, k))
    u = (TAU[None, :] - (1 - p)) / np.clip(p, 1e-9, None)
    q = wet + stats.gamma.ppf(np.clip(u, 0, 1 - 1e-9), k, scale=m / k)
    return np.where(u > 0, q, 0.0)


def hurdle_exceed(p, m, k, wet, thr):
    p, m, k = (np.asarray(a, float) for a in (p, m, k))
    return p * stats.gamma.sf(max(thr - wet, 0.0), k, scale=m / k)
