"""Reference forecasts: climatology, persistence, raw, lapse, EMOS."""

import logging

import numpy as np
import pandas as pd
from scipy import optimize, special

from gnostiq import align, dist, physics

log = logging.getLogger("gnostiq")

HVARS = {"t2m": ("o_t2m", "f_t2m", "t_prior"), "td2m": ("o_td2m", "f_td2m", "td_prior")}


def cyc(t, lon=0.0):
    t = pd.DatetimeIndex(t)
    h = 2 * np.pi * ((t.hour + t.minute / 60 + lon / 15) % 24) / 24
    d = 2 * np.pi * t.day_of_year / 365.25
    return h, d


def clim_design(t, lon):
    h, d = cyc(t, lon)
    sh, ch, sd, cd = np.sin(h), np.cos(h), np.sin(d), np.cos(d)
    cols = [np.ones(len(h)), sd, cd, np.sin(2 * d), np.cos(2 * d), sh, ch, np.sin(2 * h), np.cos(2 * h)]
    cols += [sd * sh, sd * ch, cd * sh, cd * ch]
    return np.column_stack(cols)


def clim_hourly(c, obs, col, valid):
    tr = obs[(obs.valid <= pd.Timestamp(c.window.train_end) + pd.Timedelta(hours=23)) & obs[col].notna()]
    beta, *_ = np.linalg.lstsq(clim_design(tr.valid, c.site.lon), tr[col].to_numpy(), rcond=None)
    res = tr[col].to_numpy() - clim_design(tr.valid, c.site.lon) @ beta
    sd = pd.Series(res).groupby(tr.valid.dt.month.to_numpy()).std()
    mu = clim_design(valid, c.site.lon) @ beta
    sigma = pd.DatetimeIndex(valid).month.map(sd).to_numpy(float)
    return mu, np.where(np.isfinite(sigma), sigma, np.nanstd(res))


def emos_design(p, prior, lon, extra=()):
    h, d = cyc(p.valid, lon)
    # a missing extra model counts as agreeing with the base
    alt = [p[k].fillna(0.0).to_numpy(float) for k in extra]
    x = np.column_stack([np.ones(len(p)), p[prior].to_numpy(float), *alt, np.sin(h), np.cos(h), np.sin(d), np.cos(d)])
    z = np.column_stack([np.ones(len(p)), np.sin(h), np.cos(h)])
    return x, z


def emos_fit(x, z, y):
    b0, *_ = np.linalg.lstsq(x, y, rcond=None)
    g0 = np.array([np.log(max(np.std(y - x @ b0), 0.1)), 0.0, 0.0])
    nb = x.shape[1]

    def loss(th):
        return dist.crps_norm(y, x @ th[:nb], np.exp(np.clip(z @ th[nb:], -4, 4))).mean()

    return optimize.minimize(loss, np.concatenate([b0, g0]), method="L-BFGS-B").x


def emos(c, fit, target, prior, ocol, extra=(), name="emos"):
    mu, sg = np.full(len(target), np.nan), np.full(len(target), np.nan)
    for lead in c.lead_days:
        a = fit[(fit.lead_day == lead) & fit[prior].notna() & fit[ocol].notna()]
        sel = ((target.lead_day == lead) & target[prior].notna()).to_numpy()
        if len(a) < 100:
            log.warning("%s %s lead %d: %d training rows, skipped", name, ocol, lead, len(a))
            continue
        x, z = emos_design(a, prior, c.site.lon, extra)
        th = emos_fit(x, z, a[ocol].to_numpy(float))
        x, z = emos_design(target[sel], prior, c.site.lon, extra)
        nb = x.shape[1]
        mu[sel], sg[sel] = x @ th[:nb], np.exp(np.clip(z @ th[nb:], -4, 4))
    return mu, sg


def hourly(c):
    p = pd.read_parquet(c.paths.processed / "pairs_hourly.parquet")
    obs = pd.read_parquet(c.paths.interim / "obs.parquet").rename(columns={"t": "o_t2m", "td": "o_td2m"})
    extras = align.extras(c)

    out = []
    for var, (ocol, fcol, prior) in HVARS.items():
        q = p[p[ocol].notna()].reset_index(drop=True)
        key = q[["valid", "lead_day", "split"]].assign(var=var, obs=q[ocol])

        def emit(name, mu, sigma=np.nan, key=key):
            out.append(key.assign(system=name, mu=np.asarray(mu, float), sigma=sigma))

        emit("clim", *clim_hourly(c, obs, ocol, q.valid))
        # latest obs available at issue time
        prev = obs.set_index("valid")[ocol].reindex(q.valid - pd.to_timedelta(q.lead_day, unit="D")).to_numpy()
        emit("persist", prev)
        emit("raw", q[fcol])
        emit("lapse", q[prior])
        for m, e in extras.items():
            emit(f"raw:{m}", q[["valid", "lead_day"]].merge(e, on=["valid", "lead_day"], how="left")[fcol])

        fit = q[q.split == "train"]
        emit("emos", *emos(c, fit, q, prior, ocol))
        # same method, same extra models as gnostiq gets: the fair reference for its inputs
        extra = physics.extra_deltas(q, var)
        if extra:
            emit("emos_multi", *emos(c, fit, q, prior, ocol, extra, name="emos_multi"))

    pred = pd.concat(out, ignore_index=True).dropna(subset=["mu"])
    pred.to_parquet(c.paths.processed / "pred_hourly_base.parquet", index=False)
    log.info("baselines hourly: %s", pred.groupby("system").size().to_dict())
    return pred


def rain_frame(key, p1, p10, q):
    f = key.assign(p1=np.asarray(p1, float), p10=np.asarray(p10, float))
    return pd.concat([f, pd.DataFrame(np.asarray(q, np.float32), columns=dist.QCOLS, index=f.index)], axis=1)


def point_rain(key, x, c):
    x = np.asarray(x, float)
    ok = np.isfinite(x)
    q = np.repeat(x[ok, None], len(dist.TAU), axis=1)
    return rain_frame(key[ok], x[ok] >= c.wet_mm, x[ok] >= c.heavy_mm, q)


def clim_daily(c, truth, days):
    tr = truth[truth.day <= pd.Timestamp(c.window.train_end)]
    doy = tr.day.dt.day_of_year.to_numpy()
    y = tr.tp24.to_numpy()
    tab = {}
    for d in np.unique(days.dt.day_of_year):
        gap = np.abs(doy - d)
        s = y[np.minimum(gap, 366 - gap) <= 15]
        if len(s) < 20:
            continue
        tab[d] = (np.mean(s >= c.wet_mm), np.mean(s >= c.heavy_mm), np.quantile(s, dist.TAU))
    nanq = np.full(len(dist.TAU), np.nan)
    rows = [tab.get(d, (np.nan, np.nan, nanq)) for d in days.dt.day_of_year]
    return np.array([r[0] for r in rows]), np.array([r[1] for r in rows]), np.vstack([r[2] for r in rows])


def rain_design(p):
    return np.column_stack(
        [np.ones(len(p)), p.f_tp24_sqrt.to_numpy(float), p.doy_s.to_numpy(float), p.doy_c.to_numpy(float)]
    )


def rain_emos_fit(a, y, wet):
    w = y >= wet

    def nll_occ(b):
        eta = a @ b
        return np.mean(np.logaddexp(0, eta) - w * eta) + 1e-3 * b @ b

    b = optimize.minimize(nll_occ, np.zeros(a.shape[1]), method="L-BFGS-B").x
    aw, yw = a[w], y[w] - wet + 0.05

    def nll_amt(th):
        k = np.exp(np.clip(th[-1], -3, 3))
        m = np.exp(np.clip(aw @ th[:-1], -3, 6))
        return -np.mean((k - 1) * np.log(yw) - yw * k / m - k * np.log(m / k) - special.gammaln(k))

    th0 = np.zeros(a.shape[1] + 1)
    th0[0] = np.log(yw.mean())
    return b, optimize.minimize(nll_amt, th0, method="L-BFGS-B").x


def rain_emos_predict(a, b, th):
    p = special.expit(a @ b)
    return p, np.exp(np.clip(a @ th[:-1], -3, 6)), np.full(len(a), np.exp(np.clip(th[-1], -3, 3)))


def hurdle_frame(key, p, m, k, c):
    return rain_frame(
        key, p, dist.hurdle_exceed(p, m, k, c.wet_mm, c.heavy_mm), dist.hurdle_quantiles(p, m, k, c.wet_mm)
    )


def daily(c):
    p = pd.read_parquet(c.paths.processed / "pairs_daily.parquet")
    truth = align.truth_rain(c)
    key = p[["day", "lead_day", "split"]].assign(obs=p.o_tp24)
    out = []

    p1, p10, q = clim_daily(c, truth, p.day)
    out.append(rain_frame(key, p1, p10, q).assign(system="clim").dropna(subset=["p1"]))
    # at lead L the last complete day is L+1 back
    prev = truth.set_index("day").tp24.reindex(p.day - pd.to_timedelta(p.lead_day + 1, unit="D")).to_numpy()
    out.append(point_rain(key, prev, c).assign(system="persist"))
    out.append(point_rain(key, p.f_tp24, c).assign(system="raw"))

    for m in c.nwp.extra:
        path = c.paths.interim / f"nwp_{m}.parquet"
        if not path.exists():
            continue
        e = physics.rain_sum(pd.read_parquet(path, columns=["valid", "lead_day", "f_tp"]), c.truth.rain_h0)
        x = p[["day", "lead_day"]].merge(e, on=["day", "lead_day"], how="left").f_tp24
        out.append(point_rain(key, x, c).assign(system=f"raw:{m}"))

    for lead in c.lead_days:
        sel = (p.lead_day == lead).to_numpy()
        tr = sel & (p.split == "train").to_numpy()
        y = p.o_tp24.to_numpy(float)
        if (y[tr] >= c.wet_mm).sum() < 30:
            log.warning("rain emos lead %d: too few wet training days, skipped", lead)
            continue
        b, th = rain_emos_fit(rain_design(p[tr]), y[tr], c.wet_mm)
        pp, m_, k_ = rain_emos_predict(rain_design(p[sel]), b, th)
        out.append(hurdle_frame(key[sel], pp, m_, k_, c).assign(system="emos"))

    pred = pd.concat(out, ignore_index=True)
    pred.to_parquet(c.paths.processed / "pred_daily_base.parquet", index=False)
    log.info("baselines daily: %s", pred.groupby("system").size().to_dict())
    return pred


def run(c):
    return hourly(c), daily(c)
