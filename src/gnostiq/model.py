"""Correction networks and losses."""

import math

import numpy as np
import torch
import torch.nn.functional as F
from torch import nn

DEP_S = 3.0  # degC
ONE = math.log(math.e - 1)  # softplus(ONE) == 1


def inv_softplus(x):
    return x + torch.log(-torch.expm1(-x))


class Net(nn.Module):
    def __init__(self, n_in, n_out, hidden, drop=0.1):
        super().__init__()
        self.body = nn.Sequential(
            nn.Linear(n_in, hidden),
            nn.SiLU(),
            nn.Dropout(drop),
            nn.Linear(hidden, hidden),
            nn.SiLU(),
            nn.Linear(hidden, n_out),
        )
        # zero init: an untrained net returns the prior
        nn.init.zeros_(self.body[-1].weight)
        nn.init.zeros_(self.body[-1].bias)

    def forward(self, x):
        return self.body(x)


class Hourly(nn.Module):
    def __init__(self, n_in, hidden, s_t, s_d):
        super().__init__()
        self.net = Net(n_in, 4, hidden)
        self.register_buffer("s_t", torch.tensor(float(s_t)))
        self.register_buffer("s_d", torch.tensor(float(s_d)))

    def forward(self, x, t_prior, dep_prior):
        o = self.net(x)
        t_mu = t_prior + self.s_t * o[:, 0]
        t_sig = self.s_t * F.softplus(ONE + o[:, 1]) + 1e-3
        dep = DEP_S * F.softplus(inv_softplus(dep_prior.clamp_min(0.05) / DEP_S) + o[:, 2])
        td_sig = self.s_d * F.softplus(ONE + o[:, 3]) + 1e-3
        return t_mu, t_sig, t_mu - dep, td_sig


class Daily(nn.Module):
    def __init__(self, n_in, hidden, logit0, eff0):
        super().__init__()
        self.net = Net(n_in, 3, hidden)
        self.register_buffer("logit0", torch.tensor(float(logit0)))
        self.register_buffer("eff0", inv_softplus(torch.tensor(float(eff0))))

    def forward(self, x):
        o = self.net(x)
        eff = F.softplus(self.eff0 + o[:, 1]) + 1e-4
        k = F.softplus(ONE + o[:, 2]) + 0.05
        return self.logit0 + o[:, 0], eff, k


def crps_norm(y, mu, sig):
    z = (y - mu) / sig
    pdf = torch.exp(-0.5 * z * z) / math.sqrt(2 * math.pi)
    cdf = 0.5 * (1 + torch.erf(z / math.sqrt(2)))
    return sig * (z * (2 * cdf - 1) + 2 * pdf - 1 / math.sqrt(math.pi))


def hourly_loss(net, x, t_prior, dep_prior, y_t, y_td):
    t_mu, t_sig, td_mu, td_sig = net(x, t_prior, dep_prior)
    has = torch.isfinite(y_td)
    td = crps_norm(torch.nan_to_num(y_td), td_mu, td_sig) * has
    return crps_norm(y_t, t_mu, t_sig).mean() + td.sum() / has.sum().clamp_min(1)


def daily_loss(net, x, pw, y, wet, eff_max):
    logit, eff, k = net(x)
    w = y >= wet
    occ = F.binary_cross_entropy_with_logits(logit, w.float(), reduction="none")
    excess = (y - wet + 0.05).clamp_min(0.05)
    amt = -torch.distributions.Gamma(k, k / (eff * pw)).log_prob(excess)
    # soft cap: convergence can rain out more than the column holds
    cap = F.relu(eff - eff_max) ** 2
    return (occ + torch.where(w, amt, torch.zeros_like(amt)) + cap).mean()


def fit_stats(df, candidates):
    feats = [f for f in candidates if f in df and df[f].notna().mean() > 0.5 and df[f].std() > 1e-9]
    x = df[feats].astype(float)
    return {"feats": feats, "med": x.median().tolist(), "mean": x.mean().tolist(), "std": x.std().tolist()}


def design(df, st):
    x = np.column_stack([df[f].to_numpy(float) if f in df else np.full(len(df), np.nan) for f in st["feats"]])
    x = np.where(np.isfinite(x), x, np.asarray(st["med"]))
    return torch.tensor((x - np.asarray(st["mean"])) / np.asarray(st["std"]), dtype=torch.float32)


def col(df, name):
    return torch.tensor(df[name].to_numpy(float), dtype=torch.float32)


def save(bundle, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(bundle, path)


def load(path):
    if not path.exists():
        raise FileNotFoundError(f"{path} missing; run `gnostiq train`")
    return torch.load(path, weights_only=True)


@torch.no_grad()
def predict_hourly(b, df):
    x, tp, dp = design(df, b["stats"]), col(df, "t_prior"), col(df, "dep_prior")
    outs = []
    for sd in b["states"]:
        net = Hourly(len(b["stats"]["feats"]), b["hidden"], b["s_t"], b["s_d"])
        net.load_state_dict(sd)
        net.eval()
        outs.append(torch.stack(net(x, tp, dp)))
    o = torch.stack(outs).numpy()  # member, output, row

    def mix(mu, sig):
        m = mu.mean(0)
        return m, np.sqrt(np.maximum((sig**2 + mu**2).mean(0) - m**2, 1e-6))

    t_mu, t_sig = mix(o[:, 0], o[:, 1])
    td_mu, td_sig = mix(o[:, 2], o[:, 3])
    return t_mu, t_sig, td_mu, td_sig


@torch.no_grad()
def predict_daily(b, df):
    x, pw = design(df, b["stats"]), df.pw.to_numpy(float)
    ps, ms, ks = [], [], []
    for sd in b["states"]:
        net = Daily(len(b["stats"]["feats"]), b["hidden"], 0.0, 1.0)
        net.load_state_dict(sd)
        net.eval()
        logit, eff, k = net(x)
        ps.append(torch.sigmoid(logit).numpy())
        ms.append(eff.numpy() * pw)
        ks.append(k.numpy())
    return np.mean(ps, 0), np.mean(ms, 0), np.mean(ks, 0)
