import json

import pandas as pd
import pytest
import synth
from conftest import SMALL, SYNTH_END, write_cfg
from fastapi.testclient import TestClient

from gnostiq import api, cfg, cli, verify
from gnostiq.ingest import nwp


@pytest.fixture(scope="module")
def repo(tmp_path_factory):
    c = cfg.load(write_cfg(tmp_path_factory.mktemp("e2e"), SMALL))
    synth.make(c, SYNTH_END, bare=True)
    mp = pytest.MonkeyPatch()
    mp.setenv("GNOSTIQ_CFG", str(c.source))
    cfg.get.cache_clear()
    cli.main(["all"])
    yield c, mp
    mp.undo()
    cfg.get.cache_clear()


def test_every_stage_left_its_output(repo):
    c, _ = repo
    for path in (
        c.paths.interim / "station.parquet",
        c.paths.interim / "obs.parquet",
        c.paths.interim / f"nwp_{c.nwp.base}.parquet",
        c.paths.processed / "pairs_hourly.parquet",
        c.paths.processed / "pairs_daily.parquet",
        c.paths.processed / "pred_hourly_base.parquet",
        c.paths.processed / "pred_daily_model.parquet",
        c.paths.models / "hourly.pt",
        c.paths.models / "daily.pt",
        c.paths.reports / "qc.md",
        c.paths.reports / "scorecard.md",
        c.paths.reports / "scorecard.json",
        c.paths.reports / "cases.json",
    ):
        assert path.exists() and path.stat().st_size > 0, path


def test_scorecard_compares_every_system_on_identical_cases(repo):
    c, _ = repo
    card = json.loads((c.paths.reports / "scorecard.json").read_text())
    for var in ("t2m", "td2m"):
        sysd = card["hourly"][var]["systems"]
        assert set(verify.CORE_H) <= set(sysd)
        assert len({sysd[s]["overall"]["n"] for s in verify.CORE_H}) == 1
        assert set(card["hourly"][var]["crpss"]) == set(verify.REFS)
    assert {"crpss", "bss1", "bss10"} == set(card["daily"]["skill"])
    assert card["hourly"]["t2m"]["crpss"]["raw"]["overall"]["skill"] > 0.3


def test_test_window_never_reached_training(repo):
    c, _ = repo
    p = pd.read_parquet(c.paths.processed / "pairs_hourly.parquet")
    assert p[p.split == "train"].valid.max() < pd.Timestamp(c.window.test_start)
    assert p[p.split == "test"].valid.min() >= pd.Timestamp(c.window.test_start)


def test_live_forecast_reaches_the_page(repo):
    c, mp = repo
    init = pd.Timestamp.now("UTC").tz_localize(None).floor("h")
    mp.setattr(nwp, "live", lambda c, days=9: (synth.live_frame(c, init), 1182.0))
    cli.main(["run"])

    client = TestClient(api.create(c))
    for url in ("/api/health", "/api/forecast", "/api/verify", "/api/cases", "/"):
        assert client.get(url).status_code == 200, url
    doc = client.get("/api/forecast").json()
    assert doc["init_utc"] == client.get("/api/health").json()["forecast_init_utc"]
    assert len(doc["hourly"]) == 24 * max(c.lead_days) and len(doc["daily"]) >= max(c.lead_days) - 1
    assert all(x["td2m"]["q50"] <= x["t2m"]["q50"] for x in doc["hourly"])
    assert [k["date"] for k in client.get("/api/cases").json()["cases"]]
