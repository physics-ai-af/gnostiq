import json

import numpy as np
import pandas as pd
import synth

from gnostiq import run
from gnostiq.ingest import nwp

INIT = pd.Timestamp("2025-07-14 09:00")


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
    monkeypatch.setattr(
        nwp, "live", lambda c, days=9: (synth.live_frame(c, pd.Timestamp.now("UTC").tz_localize(None)), 1182.0)
    )
    doc = run.run(c)
    path = c.paths.reports / "forecast.json"
    assert json.loads(path.read_text()) == doc and not list(c.paths.reports.glob("*.part"))
    assert doc["hourly"] and doc["site"]["name"] == c.site.name
