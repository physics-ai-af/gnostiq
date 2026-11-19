import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from conftest import write_cfg

from gnostiq import cfg, cli
from gnostiq.ingest import nimet

REAL = Path(__file__).parent / "data" / "nimet_65134_excerpt.json"
HOUR = pd.Timedelta(hours=1)


@pytest.fixture
def c(tmp_path):
    c = cfg.load(write_cfg(tmp_path))
    c.paths.ensure()
    return c


def feat(t, name, value, units="Celsius"):
    i = f"0-20000-0-65134-{t:%Y%m%d%H%M}-{name}"
    q = {"name": name, "value": value, "units": units, "reportTime": f"{t:%Y-%m-%dT%H:%M:%SZ}", "id": i}
    return {"geometry": {"coordinates": [8.9, 9.86667], "type": "Point"}, "id": i, "properties": q, "type": "Feature"}


def page(features, matched):
    return {"type": "FeatureCollection", "features": features, "numberMatched": matched,
            "numberReturned": len(features)}  # fmt: skip


def test_a_real_report_is_read():
    o, where = nimet.read([REAL])
    assert list(o.columns) == nimet.COLS and len(o) == 1
    row = o.loc[pd.Timestamp("2026-11-11 12:00")]
    assert (row.t, row.td, row.ps, row.slp) == (27.7, 6.8, 876.0, 1022.6) and row.wspd == pytest.approx(8.2)
    assert where == {"lon": 8.9, "lat": 9.86667, "elev": 1290.0}


def test_pull_pages_through_each_month_and_keeps_past_months(c, monkeypatch):
    t0 = pd.Timestamp("2025-03-10 12:00")
    feats = [feat(t0 + i * HOUR, "air_temperature", 20.0 + i) for i in range(5)]
    calls = []

    def fetch(url, path, params=None, max_age=None, **kw):
        assert url == nimet.ITEMS and params["wigos_station_identifier"] == "0-20000-0-65134"
        calls.append((params["datetime"], params["offset"], max_age))
        rows = feats if params["datetime"].startswith("2025-03") else []
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(page(rows[params["offset"] : params["offset"] + params["limit"]], len(rows))))
        return path

    monkeypatch.setattr(nimet, "fetch", fetch)
    monkeypatch.setattr(nimet, "LIMIT", 2)
    monkeypatch.setattr(nimet.time, "sleep", lambda s: None)
    paths = nimet.pull(c, "2025-02-01", "2025-04-30")
    assert calls[0][0] == "2025-02-01T00:00:00Z/2025-02-28T23:59:59Z"
    assert [o for d, o, _ in calls if d.startswith("2025-03")] == [0, 2, 4]
    assert len(calls) == 5 and all(age is None for _, _, age in calls)
    o, _ = nimet.read(paths)
    assert o.t.tolist() == [20.0, 21.0, 22.0, 23.0, 24.0]


def test_the_current_month_is_refetched(c, monkeypatch):
    ages = []

    def fetch(url, path, params=None, max_age=None, **kw):
        ages.append(max_age)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(page([], 0)))
        return path

    monkeypatch.setattr(nimet, "fetch", fetch)
    now = pd.Timestamp.now("UTC").tz_localize(None)
    nimet.pull(c, now - pd.Timedelta(days=40), now)
    assert ages[-1] == nimet.HOUR and ages[0] is None


def test_units_off_hour_reports_and_gross_values(c, tmp_path, monkeypatch):
    t = pd.Timestamp("2025-03-10 06:00")
    rows = [
        feat(t, "air_temperature", 300.15, "K"), feat(t, "dewpoint_temperature", 290.15, "K"),
        feat(t, "non_coordinate_pressure", 87500.0, "Pa"), feat(t + HOUR / 2, "air_temperature", 25.0),
        feat(t + HOUR, "air_temperature", 80.0), feat(t + HOUR, "dewpoint_temperature", 20.0),
        feat(t + 2 * HOUR, "air_temperature", None),
    ]  # fmt: skip
    p = tmp_path / "page.json"
    p.write_text(json.dumps(page(rows, len(rows))))
    monkeypatch.setattr(nimet, "pull", lambda c, start, end, refresh=False: [p])
    o, _ = nimet.obs(c, "2025-03-10", "2025-03-11")
    assert o.loc[t, ["t", "td", "ps"]].round(2).tolist() == [27.0, 17.0, 875.0]
    assert pd.Timestamp("2025-03-10 06:30") not in o.index
    assert np.isnan(o.loc[t + HOUR].t) and np.isnan(o.loc[t + HOUR].td)
    assert t + 2 * HOUR not in o.index


def test_an_empty_answer_is_an_empty_table(c, tmp_path):
    p = tmp_path / "page.json"
    p.write_text(json.dumps(page([], 0)))
    o, where = nimet.read([p])
    assert o.empty and list(o.columns) == nimet.COLS and where == {}


def test_distance_between_the_airport_and_the_listed_synop():
    km = nimet.km({"lat": 9.6398, "lon": 8.8691}, {"lat": 9.86667, "lon": 8.9})
    assert 24 < km < 27 and np.isnan(nimet.km({"lat": 9.0, "lon": 7.0}, {}))


def test_nimet_is_pulled_only_when_named(c, monkeypatch):
    seen = []
    monkeypatch.setattr(nimet, "pull", lambda c, refresh=False: seen.append(refresh))
    cli.main(["--config", str(c.source), "pull", "--only", "nimet", "--refresh"])
    assert seen == [True]
