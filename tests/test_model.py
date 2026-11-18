import numpy as np
import pandas as pd
import pytest
import torch

from gnostiq import model


def test_untrained_hourly_net_returns_the_prior():
    net = model.Hourly(5, 8, s_t=1.5, s_d=2.0).eval()
    t, dep = torch.tensor([20.0, 25.0]), torch.tensor([0.5, 12.0])
    t_mu, t_sig, td_mu, td_sig = net(torch.randn(2, 5), t, dep)
    assert torch.allclose(t_mu, t) and torch.allclose(td_mu, t - dep, atol=1e-4)
    assert torch.allclose(t_sig, torch.tensor(1.5), atol=2e-3) and torch.allclose(td_sig, torch.tensor(2.0), atol=2e-3)


def test_dewpoint_never_exceeds_temperature():
    torch.manual_seed(0)
    net = model.Hourly(5, 8, 1.0, 1.0).eval()
    for p in net.parameters():
        torch.nn.init.normal_(p, std=3.0)
    t_mu, _, td_mu, _ = net(torch.randn(500, 5) * 5, torch.full((500,), 20.0), torch.zeros(500))
    assert (td_mu <= t_mu).all()


def test_daily_outputs_are_physical():
    torch.manual_seed(0)
    net = model.Daily(4, 8, logit0=-1.0, eff0=0.2).eval()
    logit, eff, k = net(torch.randn(3, 4))
    assert torch.allclose(logit, torch.tensor(-1.0)) and torch.allclose(eff, torch.tensor(0.2), atol=1e-3)
    for p in net.parameters():
        torch.nn.init.normal_(p, std=3.0)
    _, eff, k = net(torch.randn(500, 4) * 5)
    assert (eff > 0).all() and (k > 0).all()


def test_inv_softplus_round_trip():
    x = torch.tensor([0.01, 0.5, 3.0, 20.0])
    assert torch.allclose(torch.nn.functional.softplus(model.inv_softplus(x)), x, atol=1e-5)


def test_crps_matches_the_closed_form_used_for_scoring():
    from gnostiq import dist

    y, mu, sig = torch.tensor([0.3, -1.0, 4.0]), torch.tensor([1.0, 0.0, 4.0]), torch.tensor([2.0, 0.5, 1.0])
    assert np.allclose(
        model.crps_norm(y, mu, sig).numpy(), dist.crps_norm(y.numpy(), mu.numpy(), sig.numpy()), atol=1e-6
    )


def test_hourly_loss_skips_missing_dewpoints():
    torch.manual_seed(0)
    net = model.Hourly(3, 8, 1.0, 1.0)
    x, t, dep, y = torch.randn(8, 3), torch.full((8,), 20.0), torch.full((8,), 4.0), torch.full((8,), 21.0)
    full = model.hourly_loss(net, x, t, dep, y, torch.full((8,), 15.0))
    none = model.hourly_loss(net, x, t, dep, y, torch.full((8,), float("nan")))
    assert torch.isfinite(full) and torch.isfinite(none) and none < full
    none.backward()
    assert all(torch.isfinite(p.grad).all() for p in net.parameters() if p.grad is not None)


def test_daily_loss_is_finite_and_the_cap_bites():
    net = model.Daily(4, 8, 0.0, 5.0)
    x, pw = torch.randn(64, 4), torch.full((64,), 40.0)
    y = torch.cat([torch.zeros(32), torch.rand(32) * 30 + 1])
    capped, loose = model.daily_loss(net, x, pw, y, 1.0, 2.0), model.daily_loss(net, x, pw, y, 1.0, 10.0)
    assert torch.isfinite(capped) and capped > loose


def test_design_imputes_and_scales():
    df = pd.DataFrame({"a": [1.0, np.nan, 3.0], "b": [5.0, 5.0, 5.0], "c": [np.nan] * 3})
    st = model.fit_stats(df, ["a", "b", "c", "missing"])
    assert st["feats"] == ["a"]
    x = model.design(pd.DataFrame({"a": [np.nan, 2.0]}), st)
    assert torch.isfinite(x).all() and x[0, 0] == x[1, 0]


def bundle(kind):
    df = pd.DataFrame({"a": np.linspace(0, 1, 20), "b": np.linspace(5, 9, 20)})
    st = model.fit_stats(df, ["a", "b"])
    torch.manual_seed(0)
    if kind == "hourly":
        states = [model.Hourly(2, 8, 1.2, 1.8).state_dict() for _ in range(2)]
        return {"kind": kind, "stats": st, "s_t": 1.2, "s_d": 1.8, "hidden": 8, "states": states}, df
    states = [model.Daily(2, 8, -0.5, 0.3).state_dict() for _ in range(2)]
    return {"kind": kind, "stats": st, "hidden": 8, "states": states}, df


def test_save_and_load_round_trip(tmp_path):
    b, _ = bundle("hourly")
    model.save(b, tmp_path / "m" / "hourly.pt")
    back = model.load(tmp_path / "m" / "hourly.pt")
    assert back["stats"] == b["stats"] and back["s_t"] == 1.2 and len(back["states"]) == 2
    with pytest.raises(FileNotFoundError, match="gnostiq train"):
        model.load(tmp_path / "absent.pt")


def test_predict_hourly_returns_one_value_per_row():
    b, df = bundle("hourly")
    df = df.assign(t_prior=22.0, dep_prior=5.0)
    t_mu, t_sig, td_mu, td_sig = model.predict_hourly(b, df)
    assert t_mu.shape == (20,) and np.allclose(t_mu, 22.0) and np.allclose(td_mu, 17.0, atol=1e-3)
    assert (t_sig > 0).all() and (td_sig > 0).all()


def test_predict_hourly_applies_the_spread_correction():
    b, df = bundle("hourly")
    df = df.assign(t_prior=22.0, dep_prior=5.0)
    plain = model.predict_hourly(b, df)
    wide = model.predict_hourly({**b, "inflate": {"t": 1.5, "td": 2.0}}, df)
    assert np.allclose(wide[0], plain[0]) and np.allclose(wide[2], plain[2])
    assert np.allclose(wide[1], 1.5 * plain[1]) and np.allclose(wide[3], 2.0 * plain[3])


def test_predict_daily_scales_amount_with_moisture():
    b, df = bundle("daily")
    p, m, k = model.predict_daily(b, df.assign(pw=np.linspace(10, 60, 20)))
    assert p.shape == (20,) and ((p > 0) & (p < 1)).all() and (k > 0).all()
    assert np.allclose(m / np.linspace(10, 60, 20), m[0] / 10)
