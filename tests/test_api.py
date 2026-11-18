import json

import pytest
from conftest import write_cfg
from fastapi.testclient import TestClient

from gnostiq import api, cfg


@pytest.fixture
def site(tmp_path):
    c = cfg.load(write_cfg(tmp_path))
    c.paths.ensure()
    return c, TestClient(api.create(c))


def test_reports_are_404_until_generated(site):
    _, client = site
    for url in ("/api/forecast", "/api/verify", "/api/cases"):
        r = client.get(url)
        assert r.status_code == 404 and "not generated yet" in r.json()["detail"]
    assert client.get("/api/health").json() == {"ok": True, "forecast_init_utc": None}


def test_reports_are_served_as_written(site):
    c, client = site
    docs = {
        "forecast.json": {"init_utc": "2026-07-14T09:00Z", "hourly": [], "daily": []},
        "scorecard.json": {"meta": {"site": "jos"}},
        "cases.json": {"cases": []},
    }
    for name, doc in docs.items():
        (c.paths.reports / name).write_text(json.dumps(doc))
    for url, name in (
        ("/api/forecast", "forecast.json"),
        ("/api/verify", "scorecard.json"),
        ("/api/cases", "cases.json"),
    ):
        r = client.get(url)
        assert r.status_code == 200 and r.json() == docs[name] and "max-age" in r.headers["cache-control"]
    assert client.get("/api/health").json()["forecast_init_utc"] == "2026-07-14T09:00Z"


def test_page_is_served_and_talks_to_the_api(site):
    _, client = site
    r = client.get("/")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/html")
    for url in ("/api/forecast", "/api/verify", "/api/cases"):
        assert url in r.text
    assert "Open-Meteo" in r.text and "CHIRPS" in r.text
    # the site comes from the data, so one page serves any site
    assert "Jos" not in r.text and "f.site.name" in r.text and "j.meta.site" in r.text


def test_method_note_is_served_when_present(site):
    c, client = site
    assert client.get("/method").status_code == 404
    (c.source.parent / "docs").mkdir()
    (c.source.parent / "docs" / "METHOD.md").write_text("# Method note\n")
    r = client.get("/method")
    assert r.status_code == 200 and r.text.startswith("# Method note")


def test_no_interactive_docs_are_exposed(site):
    _, client = site
    assert client.get("/docs").status_code == 404 and client.get("/openapi.json").status_code == 200
