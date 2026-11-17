import numpy as np
import pandas as pd
import torch

from gnostiq import dist, model, physics, train, verify


def test_validation_split_holds_out_whole_weeks():
    days = pd.date_range("2024-01-01", "2024-12-29", freq="D")  # 52 full weeks, Monday start
    hold = train.val_mask(days)
    weeks = pd.Series(hold).groupby(np.arange(len(days)) // 7)
    assert (weeks.nunique() == 1).all()
    assert 0.17 < hold.mean() < 0.23
    hours = pd.date_range("2024-03-04", periods=48, freq="h")
    assert len(set(train.val_mask(hours))) == 1


def test_loop_stops_after_patience_and_keeps_the_best_weights(raw):
    from dataclasses import replace

    c = replace(raw, model=replace(raw.model, max_epochs=50, patience=4))
    net = torch.nn.Linear(3, 1)
    x = torch.randn(64, 3)
    # best at epoch 3
    scripted = [5.0, 4.0, 3.0, 3.5, 3.6, 3.7, 3.8, 3.9, 4.0]
    seen = []

    def loss(net, x):
        if net.training:
            return (net(x) ** 2).mean()
        seen.append(net.weight.detach().clone())
        return torch.tensor(scripted[len(seen) - 1])

    state, best = train.loop(net, loss, (x,), (x,), c, seed=0)
    assert best == 3.0 and len(seen) == 3 + 4
    assert torch.equal(state["weight"], seen[2]) and not torch.equal(state["weight"], seen[-1])


def test_loop_runs_to_the_epoch_limit_while_improving(raw):
    from dataclasses import replace

    c = replace(raw, model=replace(raw.model, max_epochs=5, patience=2))
    net = torch.nn.Linear(3, 1)
    x = torch.randn(64, 3)
    calls = []

    def loss(net, x):
        if not net.training:
            calls.append(1)
            return torch.tensor(10.0 - len(calls))
        return (net(x) ** 2).mean()

    _, best = train.loop(net, loss, (x,), (x,), c, seed=0)
    assert len(calls) == 5 and best == 5.0


def test_bundles_record_what_they_were_trained_on(trained):
    c = trained
    hb, db = model.load(c.paths.models / "hourly.pt"), model.load(c.paths.models / "daily.pt")
    assert hb["kind"] == "hourly" and db["kind"] == "daily"
    assert len(hb["states"]) == c.model.seeds and hb["hidden"] == c.model.hidden and hb["base"] == c.nwp.base
    assert hb["train_end"] == str(c.window.train_end) and hb["s_t"] > 0
    assert set(hb["stats"]["feats"]) <= set(physics.HOURLY_FEATS) and set(db["stats"]["feats"]) <= set(
        physics.DAILY_FEATS
    )


def test_trains_without_fields_the_archive_lacks(trained):
    c = trained
    hb = model.load(c.paths.models / "hourly.pt")
    assert "f_t850" not in hb["cols"] and "f_cape" not in hb["cols"] and "f_sw" in hb["cols"]
    assert "gamma" not in hb["stats"]["feats"] and "f_cape" not in hb["stats"]["feats"]
    d = pd.read_parquet(c.paths.processed / "pairs_daily.parquet")
    assert d.tcwv_max.isna().all() and d.pw.notna().all()


def test_hourly_predictions_respect_the_dewpoint_constraint(trained):
    c = trained
    p = pd.read_parquet(c.paths.processed / "pred_hourly_model.parquet")
    assert set(p.system) == {"gnostiq"} and set(p["var"]) == {"t2m", "td2m"} and (p.sigma > 0).all()
    wide = p.pivot(index=["valid", "lead_day"], columns="var", values="mu").dropna()
    assert (wide.td2m <= wide.t2m).all()


def test_rain_predictions_are_coherent(trained):
    c = trained
    p = pd.read_parquet(c.paths.processed / "pred_daily_model.parquet")
    q = p[dist.QCOLS].to_numpy()
    assert (np.diff(q, axis=1) >= -1e-6).all() and (q >= 0).all()
    assert ((p.p10 <= p.p1 + 1e-9) & (p.p1 <= 1) & (p.p10 >= 0)).all()


def test_scorecard_scores_the_model_against_each_reference(trained):
    card = verify.run(trained)
    for var in ("t2m", "td2m"):
        sysd = card["hourly"][var]["systems"]
        assert len({sysd[s]["overall"]["n"] for s in verify.CORE_H}) == 1
        assert set(card["hourly"][var]["crpss"]) == set(verify.REFS)
    d = card["daily"]
    assert len({d["systems"][s]["overall"]["n"] for s in verify.CORE_D}) == 1
    assert set(d["skill"]) == {"crpss", "bss1", "bss10"} and set(d["reliability"]) == {"gnostiq", "emos"}
    sk = card["hourly"]["t2m"]["crpss"]["raw"]["overall"]
    assert sk["lo"] <= sk["skill"] <= sk["hi"]
    # the synthetic run is 2 degC warm
    assert sk["skill"] > 0.3
