import json

import pytest
from conftest import write_cfg, write_nearby
from fastapi.testclient import TestClient

from gnostiq import api, cfg


@pytest.fixture
def site(tmp_path):
    c = cfg.load(write_cfg(tmp_path))
    c.paths.ensure()
    return c, TestClient(api.create(c))


def test_reports_are_404_until_generated(site):
    _, client = site
    for url in ("/api/forecast", "/api/verify", "/api/cases", "/api/live"):
        r = client.get(url)
        assert r.status_code == 404 and "not generated yet" in r.json()["detail"]
    assert client.get("/api/health").json() == {"ok": True, "forecast_init_utc": None, "sites": {"jos": None}}


def test_reports_are_served_as_written(site):
    c, client = site
    docs = {
        "forecast.json": {"init_utc": "2026-07-14T09:00Z", "hourly": [], "daily": []},
        "scorecard.json": {"meta": {"site": "jos"}},
        "cases.json": {"cases": []},
        "live.json": {"site": "jos", "vars": {}},
        "season.json": {"site": "jos", "window": ["2026-04-01", "2026-10-31"]},
    }
    for name, doc in docs.items():
        (c.paths.reports / name).write_text(json.dumps(doc))
    pairs = [("/api/forecast", "forecast.json"), ("/api/verify", "scorecard.json"), ("/api/cases", "cases.json"),
             ("/api/live", "live.json"), ("/api/jos/season", "season.json")]  # fmt: skip
    for url, name in pairs:
        r = client.get(url)
        assert r.status_code == 200 and r.json() == docs[name] and "max-age" in r.headers["cache-control"]
    assert client.get("/api/health").json()["forecast_init_utc"] == "2026-07-14T09:00Z"


def test_page_is_served_and_talks_to_the_api(site):
    _, client = site
    r = client.get("/")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/html")
    assert "/api/sites" in r.text and "/api/${SITE.name}/${kind}" in r.text
    for kind in ("forecast", "verify", "cases", "live", "season"):
        assert f'api("{kind}")' in r.text
    assert "Open-Meteo" in r.text and "CHIRPS" in r.text
    # the sites come from the configs, so one page serves any of them
    assert "Jos" not in r.text and "Abuja" not in r.text


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


def test_every_site_beside_the_config_is_served(tmp_path):
    c = cfg.load(write_cfg(tmp_path))
    near = cfg.load(write_nearby(tmp_path))
    for x in (c, near):
        x.paths.ensure()
        (x.paths.reports / "forecast.json").write_text(json.dumps({"init_utc": x.site.name, "hourly": []}))
    client = TestClient(api.create(c))
    sites = client.get("/api/sites").json()
    assert all(s["compare"] == list(c.nwp.compare) for s in sites)
    assert [(s["name"], s["trained_at"], s["config"]) for s in sites] == [
        ("jos", "jos", "gnostiq.toml"), ("nearby", "jos", "gnostiq-nearby.toml")]  # fmt: skip
    assert client.get("/api/nearby/forecast").json()["init_utc"] == "nearby"
    assert client.get("/api/forecast").json()["init_utc"] == "jos"
    assert client.get("/api/health").json()["sites"] == {"jos": "jos", "nearby": "nearby"}
    r = client.get("/api/nearby/verify")
    assert r.status_code == 404 and "not generated yet for nearby" in r.json()["detail"]
    assert client.get("/api/elsewhere/forecast").status_code == 404
    assert client.get("/api/jos/secrets").status_code == 404
