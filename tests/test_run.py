import gzip
import json
import shutil

import numpy as np
import pandas as pd
import pytest
import synth
from conftest import LIVE, add_nearby, drop_nearby

from gnostiq import cfg, cli, model, run
from gnostiq.ingest import nwp, static

INIT = pd.Timestamp("2025-07-14 09:00")


def live_extras(c, init, empty=False):
    f = synth.live_frame(c, init, seed=2)[["valid", "f_t2m", "f_td2m"]]
    return {m: f.iloc[:0] if empty else f for m in c.nwp.extra}


def test_live_steps_round_up_to_the_next_lead_day():
    valid = pd.DatetimeIndex(["2025-07-14 10:00", "2025-07-15 09:00", "2025-07-15 10:00", "2025-07-21 09:00"])
    assert list(run.lead_days(valid, INIT)) == [1, 1, 2, 7]
    assert list(run.lead_days(pd.DatetimeIndex(["2025-07-14 09:00"]), INIT)) == [1]


def test_forecast_covers_the_trained_leads_and_nothing_else(trained):
    c = trained
    doc = run.forecast(c, synth.live_frame(c, INIT), INIT)
    h, d = doc["hourly"], doc["daily"]
    top = max(c.lead_days)
    assert len(h) == 24 * top and {x["lead_day"] for x in h} == set(range(1, top + 1))
    assert h[0]["valid_utc"] == "2025-07-14T10:00Z" and doc["init_utc"] == "2025-07-14T09:00Z"
    assert len(d) == top and [x["lead_day"] for x in d] == list(range(1, top + 1))
    assert doc["base_model"] == c.nwp.base and doc["thresholds"] == {"wet_mm": c.wet_mm, "heavy_mm": c.heavy_mm}


def test_forecast_is_physically_consistent(trained):
    c = trained
    doc = run.forecast(c, synth.live_frame(c, INIT), INIT)
    for x in doc["hourly"]:
        assert x["t2m"]["q10"] <= x["t2m"]["q50"] <= x["t2m"]["q90"]
        assert all(x["td2m"][k] <= x["t2m"][k] for k in ("q10", "q50", "q90"))
    for x in doc["daily"]:
        assert 0 <= x["p_heavy"] <= x["p_wet"] <= 1 and 0 <= x["tp24"]["q50"] <= x["tp24"]["q90"]
        assert x["raw_tp24"] >= 0


def test_fields_the_archive_never_supplied_cannot_move_the_forecast(trained):
    c = trained
    frame = synth.live_frame(c, INIT)
    assert frame.f_t850.notna().all() and frame.f_cape.notna().all()
    blank = frame.assign(f_t850=np.nan, f_t700=np.nan, f_rh700=np.nan, f_cape=np.nan, f_tcwv=np.nan)
    assert run.forecast(c, frame, INIT) == run.forecast(c, blank, INIT)


def test_run_writes_the_document_atomically(trained, monkeypatch):
    c = trained
    now = pd.Timestamp.now("UTC").tz_localize(None)
    monkeypatch.setattr(nwp, "live", lambda c, days=9: (synth.live_frame(c, now), 1182.0))
    monkeypatch.setattr(nwp, "live_extra", lambda c, days=9: live_extras(c, now))
    doc = run.run(c)
    path = c.paths.reports / "forecast.json"
    assert json.loads(path.read_text()) == doc and not list(c.paths.reports.glob("*.part"))
    assert doc["hourly"] and doc["site"]["name"] == c.site.name
    stem = c.paths.archive / f"{pd.Timestamp(doc['init_utc'].rstrip('Z')):%Y%m%dT%H}"
    assert pd.read_parquet(stem.with_suffix(".parquet")).equals(run.issued(doc))
    # the page's own bytes, kept for the public record
    assert gzip.decompress(stem.with_suffix(".json.gz").read_bytes()) == path.read_bytes()


def test_the_forecast_carries_other_models_and_the_normal_range(trained):
    c = trained
    doc = run.forecast(c, synth.live_frame(c, INIT), INIT, live_extras(c, INIT))
    m = c.nwp.extra[0]
    first = doc["hourly"][0]
    assert set(first["models"]) == {m} and first["models"][m]["t2m"] is not None
    for var in ("t2m", "td2m"):
        q = first["clim"][var]
        assert q["q10"] < q["q50"] < q["q90"]
    assert all(set(s["models"]) == {m} for s in doc["hourly"])


def test_issued_rows_are_what_the_page_shows(trained):
    c = trained
    doc = run.forecast(c, synth.live_frame(c, INIT), INIT, live_extras(c, INIT))
    t = run.issued(doc)
    m = c.nwp.extra[0]
    assert set(t.system) == {"gnostiq", "raw", "lapse", f"raw:{m}", "clim"} and set(t["var"]) == {"t2m", "td2m"}
    assert len(t) == 2 * 5 * len(doc["hourly"]) and (t.init == INIT).all()
    first = doc["hourly"][0]
    g = t[(t.system == "gnostiq") & (t["var"] == "t2m")].iloc[0]
    assert g.mu == first["t2m"]["q50"] and g.sigma > 0
    assert (g.q10, g.q90) == (first["t2m"]["q10"], first["t2m"]["q90"])
    assert t[t.system.str.startswith("raw")][["sigma", "q10", "q90"]].isna().all().all()


def test_extra_models_feed_the_forecast_and_a_missing_one_is_survivable(trained):
    c = trained
    frame = synth.live_frame(c, INIT)
    assert any(k.startswith("x_") for k in model.load(c.paths.models / "hourly.pt")["stats"]["feats"])
    for extras in (live_extras(c, INIT), live_extras(c, INIT, empty=True)):
        doc = run.forecast(c, frame, INIT, extras)
        assert len(doc["hourly"]) == 24 * max(c.lead_days)
        assert all(x["td2m"]["q50"] <= x["t2m"]["q50"] for x in doc["hourly"])


@pytest.fixture
def nearby(trained):
    # a second site beside the trained one, with its own terrain height and no record
    c = add_nearby(trained.source.parent)
    c.paths.ensure()
    shutil.copy(trained.paths.processed / "static.json", c.paths.processed / "static.json")
    yield c
    shutil.rmtree(c.paths.data)
    drop_nearby(trained.source.parent)


def test_a_borrowing_site_runs_the_donor_networks_at_its_own_height(trained, nearby):
    home = run.forecast(trained, synth.live_frame(trained, INIT), INIT)
    doc = run.forecast(nearby, synth.live_frame(nearby, INIT), INIT)
    assert home["trained_at"] == "jos" and doc["trained_at"] == "jos" and doc["site"]["name"] == "nearby"
    assert len(doc["hourly"]) == len(home["hourly"]) and "clim" not in doc["hourly"][0]
    # same model input at a site 105 m higher: the height correction cools it
    assert doc["hourly"][0]["lapse"]["t2m"] < home["hourly"][0]["lapse"]["t2m"]
    assert all(x["lapse"]["td2m"] <= x["lapse"]["t2m"] for x in doc["hourly"])


def test_run_fetches_the_terrain_height_first(nearby, monkeypatch):
    def boom(c, refresh=False):
        raise LookupError(c.site.name)

    monkeypatch.setattr(static, "pull", boom)
    with pytest.raises(LookupError, match="nearby"):
        run.run(nearby)


def test_run_all_sites_keeps_going_past_a_failure(trained, nearby, monkeypatch):
    seen = []

    def fake(c):
        seen.append(c.site.name)
        if c.site.name == "jos":
            raise RuntimeError("down")

    monkeypatch.setattr(run, "run", fake)
    with pytest.raises(SystemExit, match="run failed for jos"):
        cli.main(["--config", str(trained.source), "run", "--all-sites"])
    assert seen == ["jos", "nearby"]


def test_pull_on_a_borrowing_site_fetches_only_its_terrain(nearby, monkeypatch):
    seen = []
    monkeypatch.setattr(static, "pull", lambda c, refresh=False: seen.append(c.site.name))
    cli.main(["--config", str(nearby.source), "--site", "nearby", "pull"])
    assert seen == ["nearby"]


def test_the_repo_jos_config_borrows_abuja():
    j = cfg.load(LIVE, "jos")
    assert j.donor == "abuja" and j.paths.data != cfg.load(LIVE).paths.data
