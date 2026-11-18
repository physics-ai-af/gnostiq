"""Network training."""

import copy
import logging

import numpy as np
import pandas as pd
import torch
from scipy import optimize

from gnostiq import baselines, dist, model, physics

log = logging.getLogger("gnostiq")

BATCH = 512


def val_mask(day):
    # hold out whole weeks; hours within a week are too alike to split
    week = (pd.DatetimeIndex(day).normalize() - pd.Timestamp("2000-01-03")).days // 7
    return np.asarray(week % 5 == 2)


def loop(net, loss_fn, tr, va, c, seed, quiet=False):
    torch.manual_seed(seed)
    opt = torch.optim.Adam(net.parameters(), lr=3e-3, weight_decay=1e-4)
    n = len(tr[0])
    best, state, stale = np.inf, None, 0
    epochs = 0
    for _ in range(c.model.max_epochs):
        epochs += 1
        net.train()
        perm = torch.randperm(n)
        for i in range(0, n, BATCH):
            idx = perm[i : i + BATCH]
            opt.zero_grad()
            loss_fn(net, *(t[idx] for t in tr)).backward()
            opt.step()
        net.eval()
        with torch.no_grad():
            v = float(loss_fn(net, *va))
        if v < best - 1e-5:
            best, state, stale = v, copy.deepcopy(net.state_dict()), 0
        else:
            stale += 1
            if stale >= c.model.patience:
                break
    if not quiet:
        log.info("  seed %d: %d epochs, validation loss %.4f", seed, epochs, best)
    return state, best


def stamp(c, tr):
    return {
        # inputs the archive actually had
        "cols": [k for k in physics.NWP_COLS if k in tr and tr[k].notna().mean() > 0.5],
        "trained": pd.Timestamp.now("UTC").strftime("%Y-%m-%dT%H:%MZ"),
        "base": c.nwp.base,
        "hidden": c.model.hidden,
        "train_end": str(c.window.train_end),
    }


def spread_factor(y, mu, sig):
    ok = np.isfinite(y) & np.isfinite(mu) & (sig > 0)
    if ok.sum() < 50:
        return 1.0
    res = optimize.minimize_scalar(
        lambda k: dist.crps_norm(y[ok], mu[ok], k * sig[ok]).mean(), bounds=(0.5, 3.0), method="bounded"
    )
    return float(res.x)


def hourly_pairs(c):
    p = pd.read_parquet(c.paths.processed / "pairs_hourly.parquet")
    return p[p.t_prior.notna() & p.dep_prior.notna() & p.o_t2m.notna()].reset_index(drop=True)


def fit_hourly(c, tr, hold, quiet=False):
    st = model.fit_stats(tr, physics.HOURLY_FEATS + physics.extra_feats(c.nwp.extra))
    s_t = float((tr.o_t2m - tr.t_prior).std())
    s_d = float((tr.o_td2m - tr.td_prior).std())
    s_d = s_d if np.isfinite(s_d) and s_d > 0 else s_t

    def pack(df):
        return (model.design(df, st), model.col(df, "t_prior"), model.col(df, "dep_prior"),
                model.col(df, "o_t2m"), model.col(df, "o_td2m"))  # fmt: skip

    a, b = pack(tr[~hold]), pack(tr[hold])
    if not quiet:
        log.info("train hourly: %d fit rows, %d validation rows, %d features", len(a[0]), len(b[0]), len(st["feats"]))
    states = []
    for seed in range(c.model.seeds):
        net = model.Hourly(len(st["feats"]), c.model.hidden, s_t, s_d)
        states.append(loop(net, model.hourly_loss, a, b, c, seed, quiet)[0])
    bundle = {"kind": "hourly", "stats": st, "s_t": s_t, "s_d": s_d, "states": states, **stamp(c, tr)}

    # sigma is learned on rows the nets have seen; rescale it on the held-out weeks
    va = tr[hold]
    t_mu, t_sig, td_mu, td_sig = model.predict_hourly(bundle, va)
    bundle["inflate"] = {
        "t": spread_factor(va.o_t2m.to_numpy(float), t_mu, t_sig),
        "td": spread_factor(va.o_td2m.to_numpy(float), td_mu, td_sig),
    }
    if not quiet:
        log.info("  spread x%.2f t2m, x%.2f td2m", bundle["inflate"]["t"], bundle["inflate"]["td"])
    return bundle


def hourly(c):
    p = hourly_pairs(c)
    tr = p[p.split == "train"]
    bundle = fit_hourly(c, tr, val_mask(tr.valid))
    model.save(bundle, c.paths.models / "hourly.pt")

    t_mu, t_sig, td_mu, td_sig = model.predict_hourly(bundle, p)
    key = p[["valid", "lead_day", "split"]]
    pred = pd.concat(
        [
            key.assign(var="t2m", obs=p.o_t2m, system="gnostiq", mu=t_mu, sigma=t_sig),
            key.assign(var="td2m", obs=p.o_td2m, system="gnostiq", mu=td_mu, sigma=td_sig),
        ],
        ignore_index=True,
    ).dropna(subset=["obs"])
    pred.to_parquet(c.paths.processed / "pred_hourly_model.parquet", index=False)
    return bundle


def daily(c):
    p = pd.read_parquet(c.paths.processed / "pairs_daily.parquet")
    p = p[p.pw.notna() & p.f_tp24.notna()].reset_index(drop=True)
    tr = p[p.split == "train"]
    st = model.fit_stats(tr, physics.DAILY_FEATS)
    wet = tr.o_tp24 >= c.wet_mm
    if wet.sum() < 30:
        raise ValueError(f"only {int(wet.sum())} wet training days; the rain model needs a full wet season")
    freq = float(np.clip(wet.mean(), 0.02, 0.98))
    logit0 = float(np.log(freq / (1 - freq)))
    eff0 = float(((tr.o_tp24[wet] - c.wet_mm + 0.05) / tr.pw[wet]).mean())

    def pack(df):
        return model.design(df, st), model.col(df, "pw"), model.col(df, "o_tp24")

    def loss(net, x, pw, y):
        return model.daily_loss(net, x, pw, y, c.wet_mm, c.model.eff_max)

    hold = val_mask(tr.day)
    a, b = pack(tr[~hold]), pack(tr[hold])
    log.info("train daily: %d fit rows, %d validation rows, %d features", len(a[0]), len(b[0]), len(st["feats"]))
    states = []
    for seed in range(c.model.seeds):
        net = model.Daily(len(st["feats"]), c.model.hidden, logit0, eff0)
        states.append(loop(net, loss, a, b, c, seed)[0])

    bundle = {"kind": "daily", "stats": st, "states": states, **stamp(c, tr)}
    model.save(bundle, c.paths.models / "daily.pt")

    pp, m, k = model.predict_daily(bundle, p)
    key = p[["day", "lead_day", "split"]].assign(obs=p.o_tp24)
    pred = baselines.hurdle_frame(key, pp, m, k, c).assign(system="gnostiq")
    pred.to_parquet(c.paths.processed / "pred_daily_model.parquet", index=False)
    return bundle


def run(c):
    return hourly(c), daily(c)
