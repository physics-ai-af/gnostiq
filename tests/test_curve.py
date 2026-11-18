import json

import numpy as np
import pandas as pd

from gnostiq import curve, train


def test_sizes_grow_and_end_with_everything():
    assert curve.sizes(60) == [("1 mo", 4), ("2 mo", 9), ("3 mo", 13), ("6 mo", 26), ("all", 60)]
    assert curve.sizes(10) == [("1 mo", 4), ("2 mo", 9), ("all", 10)]


def test_weeks_start_on_monday():
    w = curve.weeks(pd.DatetimeIndex(["2025-03-02 23:00", "2025-03-03 00:00", "2025-03-09 23:00"]))
    assert w[0] + 1 == w[1] == w[2]


def test_curve_refits_on_nested_weeks_and_scores_the_same_cases(based):
    c = based
    doc = curve.run(c)
    rows = pd.DataFrame(doc["rows"])
    assert set(rows["var"]) == {"t2m", "td2m"} and rows["size"].iloc[-1] == "all"
    for _, g in rows.groupby("var"):
        assert g.weeks.is_monotonic_increasing and g.pairs.is_monotonic_increasing
        assert g.cases.nunique() == 1
    pool = train.hourly_pairs(c)
    assert rows.pairs.max() == (pool.split == "train").sum()
    for r in doc["rows"]:
        assert {"clim", "emos", "emos_multi", "gnostiq"} == set(r["crps"]) and all(
            np.isfinite(list(r["crps"].values()))
        )
        assert set(r["skill"]) == set(curve.REFS)
        assert all(s is None or s["lo"] <= s["skill"] <= s["hi"] for s in r["skill"].values())
    assert json.loads((c.paths.reports / "curve.json").read_text()) == doc
    md = (c.paths.reports / "curve.md").read_text()
    assert md.startswith(f"# Learning curve: {c.site.name}") and "| 1 mo |" in md and "| all |" in md
