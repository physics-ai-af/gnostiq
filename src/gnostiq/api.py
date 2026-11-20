"""Read-only API over the report files."""

import html
import json
import shutil
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse

from gnostiq import cfg

WEB = Path(__file__).parent / "web"
REPORTS = {
    "forecast": "forecast.json",
    "verify": "scorecard.json",
    "cases": "cases.json",
    "live": "live.json",
    "season": "season.json",
    "records": "records.json",
}


def listing(sites):
    return [{"name": n, "trained_at": x.donor or n, "lat": x.site.lat, "lon": x.site.lon,
             "elev_m": x.site.elev, "compare": list(x.nwp.compare)} for n, x in sites.items()]  # fmt: skip


def method_note(c):
    path = c.source.parent / "docs" / "METHOD.md"
    return path.read_text(encoding="utf-8") if path.exists() else None


def export(c, out):
    # the same page and reports as plain files, laid out like the API, for a static host
    out = Path(out)
    sites = {x.site.name: x for x in cfg.sites(c)}
    (out / "api").mkdir(parents=True, exist_ok=True)
    shutil.copy(WEB / "index.html", out / "index.html")
    (out / ".nojekyll").write_text("")
    (out / "api" / "sites").write_text(json.dumps(listing(sites)))
    n = 0
    for name, x in sites.items():
        (out / "api" / name).mkdir(exist_ok=True)
        for kind, file in REPORTS.items():
            if (x.paths.reports / file).exists():
                shutil.copy(x.paths.reports / file, out / "api" / name / kind)
                n += 1
    note = method_note(c)
    if note is not None:
        (out / "method").mkdir(exist_ok=True)
        (out / "method" / "index.html").write_text(
            '<!DOCTYPE html><meta charset="utf-8"><title>Gnostiq method note</title>'
            '<pre style="white-space:pre-wrap;max-width:80ch;margin:2em auto;font:15px/1.5 system-ui,sans-serif">'
            f"{html.escape(note)}</pre>\n",
            encoding="utf-8",
        )
    return n


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
    def site_list():
        return listing(sites)

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
        note = method_note(c)
        if note is None:
            raise HTTPException(404, "method note not found")
        return note

    @app.get("/")
    def index():
        return FileResponse(WEB / "index.html")

    return app
