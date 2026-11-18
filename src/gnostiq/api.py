"""Read-only API over the report files."""

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse

from gnostiq import cfg

WEB = Path(__file__).parent / "web"


def create(c=None):
    c = c or cfg.get()
    app = FastAPI(title="gnostiq", docs_url=None, redoc_url=None)

    def report(name):
        path = c.paths.reports / name
        if not path.exists():
            raise HTTPException(404, f"{name} not generated yet")
        return JSONResponse(json.loads(path.read_text()), headers={"Cache-Control": "public, max-age=300"})

    @app.get("/api/forecast")
    def forecast():
        return report("forecast.json")

    @app.get("/api/verify")
    def verify():
        return report("scorecard.json")

    @app.get("/api/cases")
    def cases():
        return report("cases.json")

    @app.get("/api/live")
    def live():
        return report("live.json")

    @app.get("/api/health")
    def health():
        f = c.paths.reports / "forecast.json"
        init = json.loads(f.read_text())["init_utc"] if f.exists() else None
        return {"ok": True, "forecast_init_utc": init}

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
