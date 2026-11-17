import json

import pandas as pd

from gnostiq import align, cases


def test_replays_the_wettest_fully_forecast_test_days(trained):
    c = trained
    out = cases.run(c)
    assert out["heavy_mm"] == c.heavy_mm and 1 <= len(out["cases"]) <= cases.N_CASES
    obs = [k["obs_mm"] for k in out["cases"]]
    assert obs == sorted(obs, reverse=True)

    truth = align.truth_rain(c).set_index("day").tp24
    for case in out["cases"]:
        day = pd.Timestamp(case["date"])
        assert pd.Timestamp(c.window.test_start) <= day <= pd.Timestamp(c.window.test_end)
        assert case["obs_mm"] == round(float(truth[day]), 1)
    in_test = truth[str(c.window.test_start) : str(c.window.test_end)]
    assert obs[0] >= in_test.quantile(0.9)


def test_each_replay_runs_from_the_longest_lead_to_the_shortest(trained):
    c = trained
    out = cases.run(c)
    for case in out["cases"]:
        assert set(case["systems"]) == set(cases.SYSTEMS)
        for rows in case["systems"].values():
            assert [r["lead_day"] for r in rows] == sorted(c.lead_days, reverse=True)
            assert all(0 <= r["p_heavy"] <= r["p_wet"] <= 1 and r["q50"] <= r["q90"] for r in rows)
    assert json.loads((c.paths.reports / "cases.json").read_text()) == out
