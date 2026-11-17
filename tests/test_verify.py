import json

import numpy as np
import pandas as pd
import pytest

from gnostiq import verify


def test_ets():
    ob = np.array([True, False, True, False, False, True])
    assert verify.ets(ob, ob) == 1.0
    assert verify.ets(~ob, ob) < 0
    assert np.isnan(verify.ets(np.zeros(6, bool), np.zeros(6, bool)))


def test_boot_skill():
    rng = np.random.default_rng(0)
    day = np.repeat(np.arange(50), 4)
    b = rng.random(200) + 1
    same = verify.boot_skill(day, b, b, rng)
    assert same["skill"] == 0 and same["lo"] == 0 and same["hi"] == 0
    half = verify.boot_skill(day, b / 2, b, rng)
    assert abs(half["skill"] - 0.5) < 1e-9 and half["days"] == 50
    assert verify.boot_skill(day[:8], b[:8], b[:8], rng) is None


def test_boot_interval_widens_with_fewer_days():
    rng = np.random.default_rng(1)
    a, b = rng.random(400), rng.random(400) + 0.2
    many = verify.boot_skill(np.arange(400), a, b, rng)
    few = verify.boot_skill(np.arange(40), a[:40], b[:40], rng)
    assert few["hi"] - few["lo"] > many["hi"] - many["lo"]


def test_reliability_bins():
    rows = verify.reliability(np.array([0.05, 0.05, 0.95, 1.0]), np.array([0, 1, 1, 1]))
    assert [r["bin"] for r in rows] == [0, 9] and rows[0]["freq"] == 0.5 and rows[1]["n"] == 2


def test_common_keeps_only_cases_every_core_system_forecast():
    rows = [("a", 1, "x"), ("a", 1, "y"), ("b", 1, "x"), ("b", 1, "extra"), ("a", 1, "extra")]
    pred = pd.DataFrame(rows, columns=["valid", "lead_day", "system"])
    kept, have = verify.common(pred, ["valid", "lead_day"], ["x", "y", "absent"])
    assert have == ["x", "y"] and set(kept.valid) == {"a"} and set(kept.system) == {"x", "y", "extra"}


def test_skill_cell_formats_the_interval():
    assert verify.skill_cell({"skill": 0.1234, "lo": -0.01, "hi": 0.2}) == "+0.123 [-0.010, +0.200]"
    assert verify.skill_cell(None) == "-"


def test_load_names_the_missing_step(raw, tmp_path):
    from dataclasses import replace

    from gnostiq.cfg import Paths

    with pytest.raises(FileNotFoundError, match="gnostiq baselines"):
        verify.load(replace(raw, paths=Paths(tmp_path)), "hourly")


def test_scorecard_from_baselines_alone(based, tmp_path):
    import shutil
    from dataclasses import replace

    from gnostiq.cfg import Paths

    c = replace(based, paths=Paths(tmp_path))
    c.paths.ensure()
    for name in ("pred_hourly_base.parquet", "pred_daily_base.parquet"):
        shutil.copy(based.paths.processed / name, c.paths.processed / name)
    card = verify.run(c)
    assert card["meta"]["test"] == [str(c.window.test_start), str(c.window.test_end)]
    for var in ("t2m", "td2m"):
        sysd = card["hourly"][var]["systems"]
        assert {"clim", "persist", "raw", "lapse", "emos"} <= set(sysd) and "gnostiq" not in sysd
        assert len({sysd[s]["overall"]["n"] for s in ("clim", "persist", "raw", "lapse", "emos")}) == 1
        assert card["hourly"][var]["crpss"] == {}
        assert set(sysd["emos"]["by_lead"]) == set(c.lead_days)
    d = card["daily"]
    assert d["skill"] == {} and 0 < d["base_rate"]["wet"] < 1
    # point forecast: CRPS == MAE
    raw_t = card["hourly"]["t2m"]["systems"]["raw"]["overall"]
    assert raw_t["crps"] == raw_t["mae"] and raw_t["cov80"] is None
    assert json.loads((c.paths.reports / "scorecard.json").read_text())["meta"] == card["meta"]
    text = (c.paths.reports / "scorecard.md").read_text()
    assert "## t2m" in text and "## tp24" in text and "| emos |" in text
