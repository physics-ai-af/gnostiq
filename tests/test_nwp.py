import numpy as np
import pandas as pd
import pytest
from conftest import write_cfg

from gnostiq import cfg
from gnostiq.ingest import nwp
from gnostiq.io import Missing

# trimmed live response, ecmwf_ifs025, 2026-11-17
LIVE = {
    "latitude": 9.75,
    "longitude": 9.0,
    "elevation": 1182.0,
    "hourly": {
        "time": ["2024-03-01T00:00", "2024-03-01T01:00", "2024-03-01T02:00"],
        "temperature_2m_previous_day1": [23.9, 23.4, 22.9],
        "temperature_2m_previous_day7": [21.5, 20.7, 20.0],
        "dew_point_2m_previous_day1": [15.1, 15.1, 15.2],
        "precipitation_previous_day1": [0.00, 0.00, 0.00],
        "pressure_msl_previous_day1": [1012.0, 1011.8, 1011.4],
        "surface_pressure_previous_day1": [884.9, 884.5, 884.0],
        "cloud_cover_previous_day1": [30, 30, None],
    },
}


def test_parse_live_response():
    df = nwp.parse_prev(LIVE, nwp.GROUPS["core"], [1, 7])
    assert len(df) == 6 and list(df.valid[:3]) == list(pd.to_datetime(LIVE["hourly"]["time"]))
    one, seven = df[df.lead_day == 1], df[df.lead_day == 7]
    assert one.f_t2m.tolist() == [23.9, 23.4, 22.9] and seven.f_t2m.tolist() == [21.5, 20.7, 20.0]
    assert seven.f_td2m.isna().all() and np.isnan(one.f_cloud.iloc[2])


def test_chunks_cover_range_without_overlap():
    ch = list(nwp.chunks("2024-01-01", "2024-07-15", 92))
    assert str(ch[0][0]) == "2024-01-01" and str(ch[-1][1]) == "2024-07-15"
    assert all((pd.Timestamp(b[0]) - pd.Timestamp(a[1])).days == 1 for a, b in zip(ch, ch[1:], strict=False))


def test_requests_ask_for_the_raw_grid_cell(tmp_path):
    p = nwp.base_params(cfg.load(write_cfg(tmp_path)), "ecmwf_ifs025")
    assert p["elevation"] == "nan" and p["models"] == "ecmwf_ifs025" and p["timezone"] == "GMT"
    assert p["wind_speed_unit"] == "ms"


@pytest.fixture
def archive(tmp_path, monkeypatch):
    c = cfg.load(write_cfg(tmp_path, {"lead_days = [1, 2, 3, 4, 5, 6, 7]": "lead_days = [1, 7]"}))
    calls, refuse = [], set()

    def fetch(url, path, params=None, max_age=None, **kw):
        group = path.name.split("_")[0]
        calls.append((params["models"], group, params["hourly"]))
        if (params["models"], group) in refuse:
            raise Missing("400: Cannot initialize from invalid String value")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}")
        return path

    monkeypatch.setattr(nwp, "fetch", fetch)
    monkeypatch.setattr(nwp.time, "sleep", lambda s: None)
    return c, calls, refuse


def test_pull_requests_every_lead_for_every_variable(archive):
    c, calls, _ = archive
    nwp.pull(c)
    base = [x for x in calls if x[0] == "ecmwf_ifs025"]
    assert {g for _, g, _ in base} == {"core", "column", "levels"}
    hourly = next(h for _, g, h in base if g == "core").split(",")
    assert "temperature_2m_previous_day1" in hourly and "precipitation_previous_day7" in hourly
    assert len(hourly) == 2 * len(nwp.GROUPS["core"])
    assert {g for m, g, _ in calls if m != "ecmwf_ifs025"} == {"core"}


def test_pull_skips_a_refused_group_after_one_attempt(archive):
    c, calls, refuse = archive
    refuse.add(("ecmwf_ifs025", "levels"))
    nwp.pull(c)
    assert sum(1 for m, g, _ in calls if g == "levels") == 1
    marker = c.paths.raw / "nwp" / "ecmwf_ifs025" / "levels.missing"
    assert marker.exists() and "invalid String value" in marker.read_text()
    calls.clear()
    nwp.pull(c)
    assert not [x for x in calls if x[1] == "levels"]
    nwp.pull(c, refresh=True)
    assert [x for x in calls if x[1] == "levels"]


def test_pull_stops_when_the_base_model_core_is_refused(archive):
    c, _, refuse = archive
    refuse.add(("ecmwf_ifs025", "core"))
    with pytest.raises(Missing):
        nwp.pull(c)


def test_pull_tolerates_a_refused_extra_model(archive):
    c, _, refuse = archive
    refuse.add(("gfs_seamless", "core"))
    nwp.pull(c)
    assert (c.paths.raw / "nwp" / "gfs_seamless" / "core.missing").exists()


def test_build_assembles_one_row_per_valid_time_and_lead(nwp_raw):
    c = nwp_raw
    out = nwp.build(c)
    assert set(out) == {c.nwp.base, *c.nwp.extra}
    df = pd.read_parquet(c.paths.interim / f"nwp_{c.nwp.base}.parquet")
    assert not df.duplicated(["valid", "lead_day"]).any() and set(df.lead_day) == set(c.lead_days)
    assert df.valid.min() == pd.Timestamp(c.nwp.start) and df.f_t2m.notna().all()
    # as the live archive: cape/tcwv null, no levels
    assert df.f_cape.isna().all() and df.f_tcwv.isna().all() and df.f_sw.notna().all()
    assert "f_t850" not in df or df.f_t850.isna().all()
    extra = pd.read_parquet(c.paths.interim / f"nwp_{c.nwp.extra[0]}.parquet")
    assert "f_sw" not in extra


def test_build_without_chunks_says_what_to_run(tmp_path):
    with pytest.raises(FileNotFoundError, match="gnostiq pull"):
        nwp.build(cfg.load(write_cfg(tmp_path)))


def live_json(names):
    t = pd.date_range("2025-07-01", periods=4, freq="h")
    hourly = {"time": t.strftime("%Y-%m-%dT%H:%M").tolist()}
    hourly.update({n: [20.0, 21.0, None, 23.0] for n in names})
    return {"elevation": 1182.0, "hourly": hourly}


def test_live_returns_short_names_and_drops_empty_steps(tmp_path, monkeypatch):
    c = cfg.load(write_cfg(tmp_path))
    every = [v for g in nwp.GROUPS.values() for v in g.values()]
    monkeypatch.setattr(nwp, "_get", lambda url, params: live_json(every))
    df, elev = nwp.live(c)
    assert elev == 1182.0 and len(df) == 3
    assert {"valid", "f_t2m", "f_tp", "f_t850", "f_cape"} <= set(df.columns)


def test_live_falls_back_to_core_when_optional_fields_are_refused(tmp_path, monkeypatch):
    c = cfg.load(write_cfg(tmp_path))
    asked = []

    def get(url, params):
        asked.append(params["hourly"])
        if "cape" in params["hourly"]:
            raise Missing("400")
        return live_json(params["hourly"].split(","))

    monkeypatch.setattr(nwp, "_get", get)
    df, _ = nwp.live(c)
    assert len(asked) == 2 and df.f_t2m.notna().all() and df.f_cape.isna().all()
