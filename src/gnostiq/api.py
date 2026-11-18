"""Read-only API over the report files."""

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse

from gnostiq import cfg

WEB = Path(__file__).parent / "web"
REPORTS = {"forecast": "forecast.json", "verify": "scorecard.json", "cases": "cases.json", "live": "live.json"}


def create(c=None):
    c = c or cfg.get()
    sites = {x.site.name: x for x in cfg.sites(c)}
    app = FastAPI(title="gnostiq", docs_url=None, redoc_url=None)

    def report(site, kind):
        x = sites.get(site)
        if x is None or kind not in REPORTS:
            raise HTTPException(404, f"no {kind} for {site}")
        path = x.paths.reports / REPORTS[kind]
        if not path.exists():
            raise HTTPException(404, f"{path.name} not generated yet for {site}")
        return JSONResponse(json.loads(path.read_text()), headers={"Cache-Control": "public, max-age=300"})

    def init(x):
        f = x.paths.reports / "forecast.json"
        return json.loads(f.read_text())["init_utc"] if f.exists() else None

    @app.get("/api/sites")
    def listing():
        return [{"name": n, "trained_at": x.donor or n, "config": x.source.name, "lat": x.site.lat, "lon": x.site.lon,
                 "elev_m": x.site.elev} for n, x in sites.items()]  # fmt: skip

    @app.get("/api/{site}/{kind}")
    def per_site(site: str, kind: str):
        return report(site, kind)

    # the first site keeps the old single-site paths
    @app.get("/api/forecast")
    def forecast():
        return report(c.site.name, "forecast")

    @app.get("/api/verify")
    def verify():
        return report(c.site.name, "verify")

    @app.get("/api/cases")
    def cases():
        return report(c.site.name, "cases")

    @app.get("/api/live")
    def live():
        return report(c.site.name, "live")

    @app.get("/api/health")
    def health():
        return {"ok": True, "forecast_init_utc": init(c), "sites": {n: init(x) for n, x in sites.items()}}

    @app.get("/method", response_class=PlainTextResponse)
    def method():
        path = c.source.parent / "docs" / "METHOD.md"
        if not path.exists():
            raise HTTPException(404, "method note not found")
        return path.read_text()

    @app.get("/")
    def index():
        return FileResponse(WEB / "index.html")

    return app
