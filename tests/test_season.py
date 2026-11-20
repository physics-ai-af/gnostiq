import shutil

import pandas as pd
import pytest
import synth
from conftest import SYNTH_END, add_nearby, drop_nearby

from gnostiq import season
from gnostiq.ingest import nimet

START, END = "2025-04-01", "2025-06-30"


def daytime_reports(c, start, end):
    # what a daytime-only synop station would have sent, 0.1 km north of the forecast point
    tru, _ = synth.truth(c, SYNTH_END)
    o = tru.set_index("valid")[["t", "td"]]
    o = o[(o.index >= start) & (o.index <= end) & (o.index.hour >= 8) & (o.index.hour <= 17)]
    return o, {"lat": c.site.lat + 0.1, "lon": c.site.lon, "elev": c.site.elev}


@pytest.fixture
def reports(monkeypatch):
    monkeypatch.setattr(nimet, "obs", daytime_reports)


def test_every_system_is_scored_on_the_same_reports(trained, reports):
    c = trained
    out = season.run(c, START, END)
    t = out["vars"]["t2m"]
    core = {"gnostiq", "raw", "lapse", "emos", "emos_multi", "clim"}
    assert core | {f"raw:{c.nwp.extra[0]}", f"raw:{c.nwp.compare[0]}"} <= set(t["systems"])
    assert {t["systems"][s]["n"] for s in core} == {t["cases"]}
    assert set(t["skill"]) == core - {"gnostiq"} and all(s["lo"] <= s["skill"] <= s["hi"] for s in t["skill"].values())
    assert set(t["by_lead"]["gnostiq"]) == set(c.lead_days) and set(t["by_month"]["gnostiq"]) == {4, 5, 6}
    assert set(out["hours"]) == set(range(8, 18)) and out["station"]["km"] == pytest.approx(11.1, abs=0.2)
    # the synthetic model is 2 C warm; the corrections must beat it
    assert t["systems"]["gnostiq"]["crps"] < t["systems"]["raw"]["crps"]
    assert (c.paths.reports / "season.md").read_text().startswith(f"# Season: {c.site.name}, {START}")
    # day by day: a daytime-only station gives highs and no lows
    tr = out["track"]
    assert len(tr["rows"]) > 80 and all(r["obs_min"] is None for r in tr["rows"])
    sm = tr["summary"]
    assert sm["max"]["days"] == sum(r["obs_max"] is not None for r in tr["rows"]) > 80 and sm["min"]["days"] == 0
    assert sm["max"]["gnostiq"]["mae"] < sm["max"]["raw"]["mae"]
    assert sm["inside"]["n"] == sum(r["hours"] for r in tr["rows"])
    assert "## Track record" in (c.paths.reports / "season.md").read_text()


def test_a_season_inside_training_is_refused(trained):
    with pytest.raises(ValueError, match="inside the training window"):
        season.run(trained, "2024-06-01", "2024-09-30")


def test_the_default_is_the_latest_wet_season_with_a_month_in_it(trained):
    assert season.window(trained, today="2026-11-19") == (pd.Timestamp("2026-04-01"), pd.Timestamp("2026-10-31"))
    assert season.window(trained, today="2026-04-15") == (pd.Timestamp("2025-04-01"), pd.Timestamp("2025-10-31"))
    assert season.window(trained, today="2026-06-10") == (pd.Timestamp("2026-04-01"), pd.Timestamp("2026-06-09"))


def test_a_borrowing_site_is_scored_with_its_donors_fits(trained, reports):
    c = add_nearby(trained.source.parent)
    c.paths.ensure()
    shutil.copytree(trained.paths.raw / "nwp", c.paths.raw / "nwp")
    shutil.copy(trained.paths.processed / "static.json", c.paths.processed / "static.json")
    try:
        out = season.run(c, START, END)
    finally:
        shutil.rmtree(c.paths.data)
        drop_nearby(trained.source.parent)
    t = out["vars"]["t2m"]
    assert out["trained_at"] == "jos" and out["site"] == "nearby"
    # no station record of its own, so no climatology; EMOS comes from where the networks were trained
    assert "clim" not in t["systems"] and {"gnostiq", "emos", "lapse", "raw"} <= set(t["systems"])
