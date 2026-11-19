import json
import shutil

import numpy as np
import pandas as pd
import pytest
import requests
import synth

from gnostiq import dist, live, run
from gnostiq.ingest import station


def extras(c, init):
    f = synth.live_frame(c, init, seed=2)[["valid", "f_t2m", "f_td2m"]]
    return {m: f for m in c.nwp.extra}


def issue(c, init):
    t = run.issued(run.forecast(c, synth.live_frame(c, init), init, extras(c, init)))
    c.paths.archive.mkdir(parents=True, exist_ok=True)
    t.to_parquet(c.paths.archive / f"{init:%Y%m%dT%H}.parquet", index=False)
    return t


@pytest.fixture
def issued(trained):
    c = trained
    shutil.rmtree(c.paths.archive, ignore_errors=True)
    day = pd.Timestamp.now("UTC").tz_localize(None).floor("D") - pd.Timedelta(days=10)
    first = issue(c, day + pd.Timedelta(hours=2))
    issue(c, day + pd.Timedelta(hours=5))  # a later run the same day
    return c, first


def test_archive_keeps_the_first_issue_of_each_day(issued):
    c, first = issued
    a = live.archive(c)
    assert a.init.nunique() == 1 and (a.init == first.init.iloc[0]).all()


def test_check_scores_what_was_shown_against_the_reports(issued, monkeypatch):
    c, first = issued
    raw = first[(first.system == "raw")][["valid", "var", "mu"]]
    # reports 1 degree warmer than the raw model, and none for the last day
    rep = raw.assign(obs=raw.mu + 1.0).drop(columns="mu")
    rep = rep[rep.valid < rep.valid.max() - pd.Timedelta(hours=24)]
    monkeypatch.setattr(live, "reports", lambda c, since, until: rep)
    out = live.run(c)
    t = out["vars"]["t2m"]
    assert t["systems"]["raw"]["mae"] == pytest.approx(1.0) and t["systems"]["raw"]["bias"] == pytest.approx(-1.0)
    assert t["systems"]["gnostiq"]["n"] == t["systems"]["raw"]["n"] == t["systems"]["clim"]["n"] == t["cases"]
    assert t["systems"][f"raw:{c.nwp.extra[0]}"]["n"] <= t["cases"]
    assert set(t["skill"]) == {"raw", "lapse", "clim"}
    assert all(s is None or s["lo"] <= s["skill"] <= s["hi"] for s in t["skill"].values())
    assert out["reports"] == rep.valid.nunique()
    assert t["daily"] and all({"day", "gnostiq", "raw"} <= set(d) for d in t["daily"])
    assert json.loads((c.paths.reports / "live.json").read_text()) == out
    assert (c.paths.reports / "live.md").read_text().startswith(f"# Live check: {c.site.name}")


def test_the_last_week_puts_forecast_and_report_side_by_side(trained, monkeypatch):
    c = trained
    shutil.rmtree(c.paths.archive, ignore_errors=True)
    today = pd.Timestamp.now("UTC").tz_localize(None).floor("D")
    inits = [today - pd.Timedelta(days=d, hours=-2) for d in (3, 2)]
    old, new = (issue(c, i) for i in inits)
    # an archive written before the band was saved
    path = c.paths.archive / f"{inits[0]:%Y%m%dT%H}.parquet"
    pd.read_parquet(path).drop(columns=["q10", "q90"]).to_parquet(path, index=False)
    g = new[(new.system == "gnostiq") & (new["var"] == "t2m") & (new.lead_day == 1)]
    # reports on the newer issue's day-ahead hours only, a little warm; the last four fall on the next local day
    rep = g.assign(obs=g.mu + 0.3)[["valid", "var", "obs"]]
    monkeypatch.setattr(live, "reports", lambda c, since, until: rep)
    r = live.run(c)["recent"]

    assert len(r["hourly"]) == 48 and r["tz"] == c.site.tz
    by = {pd.Timestamp(h["valid_utc"].rstrip("Z")): h["t2m"] for h in r["hourly"]}
    for _, x in g.iterrows():
        assert by[x.valid]["obs"] == round(x.mu + 0.3, 1) and (by[x.valid]["q10"], by[x.valid]["q90"]) == (x.q10, x.q90)
    o = old[(old.system == "gnostiq") & (old["var"] == "t2m") & (old.lead_day == 1)].iloc[0]
    assert by[o.valid]["obs"] is None and by[o.valid]["q10"] == pytest.approx(o.mu - dist.Z80 * o.sigma, abs=0.06)
    inside = ((rep.obs >= g.q10) & (rep.obs <= g.q90)).sum()
    assert r["inside"]["t2m"] == {"n": 24, "k": int(inside)}
    day = r["daily"]
    assert [d["day"] for d in day] == [f"{inits[1]:%Y-%m-%d}"] and day[0]["reports"] == 20
    assert day[0]["obs_max"] == round(rep.obs.iloc[:20].max(), 1)
    assert "Last 7 days" in (c.paths.reports / "live.md").read_text()


def test_check_with_no_reports_at_all_says_so(issued, monkeypatch):
    c, _ = issued
    none = pd.DataFrame(
        {"valid": pd.Series(dtype="datetime64[ns]"), "obs": pd.Series(dtype=float), "var": pd.Series(dtype=str)}
    )
    monkeypatch.setattr(live, "reports", lambda c, since, until: none)
    out = live.run(c)
    assert out["reports"] == 0 and out["issues"] == 1
    assert all(v["cases"] == 0 and not v["systems"] and not v["daily"] for v in out["vars"].values())


def test_check_without_issued_forecasts_says_what_to_run(trained):
    shutil.rmtree(trained.paths.archive, ignore_errors=True)
    with pytest.raises(FileNotFoundError, match="gnostiq run"):
        live.run(trained)


def test_reports_are_converted_and_screened(trained, monkeypatch):
    c = trained
    csv = (
        "station,valid,tmpf,dwpf,alti,mslp,sknt\n"
        "DNJO,2025-07-14 12:00,77.00,68.00,30.00,M,5.00\n"
        "DNJO,2025-07-14 13:00,200.00,68.00,30.00,M,5.00\n"
        "DNJO,2025-07-14 14:00,77.00,86.00,30.00,M,5.00\n"
        "DNJO,2025-07-14 15:30,77.00,68.00,30.00,M,5.00\n"
    )

    def fake(url, path, params=None, max_age=None, **kw):
        assert url == station.IEM and params["station"] == c.site.icao and max_age == live.HOUR
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(csv)
        return path

    monkeypatch.setattr(live, "fetch", fake)
    o = live.metars(c, pd.Timestamp("2025-07-14"), pd.Timestamp("2025-07-15"))
    t = o[o["var"] == "t2m"].set_index("valid").obs
    td = o[o["var"] == "td2m"].set_index("valid").obs
    assert t.round(2).to_dict() == {pd.Timestamp("2025-07-14 12:00"): 25.0, pd.Timestamp("2025-07-14 14:00"): 25.0}
    assert td.round(2).to_dict() == {pd.Timestamp("2025-07-14 12:00"): 20.0}
    assert np.isfinite(o.obs).all() and set(o.source) == {"iem"}


def test_reports_prefer_synops_and_survive_one_source_down(trained, monkeypatch):
    t = pd.Timestamp("2025-07-14 12:00")
    hour = pd.Timedelta(hours=1)
    syn = pd.DataFrame({"valid": [t], "obs": [24.6], "var": ["t2m"], "source": ["nimet"]})
    met = pd.DataFrame({"valid": [t, t + hour], "obs": [25.0, 26.0], "var": ["t2m", "t2m"], "source": ["iem", "iem"]})
    monkeypatch.setattr(live, "synops", lambda c, a, b: syn)
    monkeypatch.setattr(live, "metars", lambda c, a, b: met)
    assert live.reports(trained, t, t).set_index("valid").obs.to_dict() == {t: 24.6, t + hour: 26.0}

    def down(c, a, b):
        raise requests.ConnectionError("timed out")

    monkeypatch.setattr(live, "synops", down)
    assert len(live.reports(trained, t, t)) == 2
    monkeypatch.setattr(live, "metars", down)
    with pytest.raises(requests.ConnectionError):
        live.reports(trained, t, t)
