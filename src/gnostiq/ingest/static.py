"""Model and station terrain heights."""

import json
import logging
import math

import numpy as np
import rasterio
from rasterio.errors import RasterioIOError
from rasterio.windows import Window

from gnostiq import physics
from gnostiq.ingest import nwp, precip

log = logging.getLogger("gnostiq")

DEM = "https://copernicus-dem-30m.s3.amazonaws.com"


def dem_url(lat, lon):
    ns, ew = ("N" if lat >= 0 else "S"), ("E" if lon >= 0 else "W")
    tile = f"Copernicus_DSM_COG_10_{ns}{abs(math.floor(lat)):02d}_00_{ew}{abs(math.floor(lon)):03d}_00_DEM"
    return f"/vsicurl/{DEM}/{tile}/{tile}.tif"


def dem(lat, lon, half=150):
    with rasterio.Env(**precip.GDAL), rasterio.open(dem_url(lat, lon)) as ds:
        row, col = ds.index(lon, lat)
        a = ds.read(
            1, window=Window(col - half, row - half, 2 * half + 1, 2 * half + 1), boundless=True, fill_value=-32767
        )
    a = a.astype(float)
    a[a < -1000] = np.nan
    return float(a[half, half]), float(np.nanmean(a))


def model_height(c):
    df, api_elev = nwp.live(c, days=3)
    z = physics.height(df.f_sp, df.f_msl, df.f_t2m).dropna()
    hyps = float(z.median()) if len(z) else None
    api = float(api_elev) if isinstance(api_elev, int | float) and math.isfinite(api_elev) else None
    return hyps, api


def pull(c, refresh=False):
    path = c.paths.processed / "static.json"
    if path.exists() and not refresh:
        return json.loads(path.read_text())
    hyps, api = model_height(c)
    out = {"z_station": c.site.elev, "z_model_hyps": hyps, "z_model_api": api, "base": c.nwp.base}
    try:
        out["z_dem_point"], out["z_dem_9km"] = dem(c.site.lat, c.site.lon)
    except (RasterioIOError, ValueError) as e:
        log.warning("DEM unavailable: %s", e)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2))
    log.info("static: %s", out)
    return out


def z_model(c):
    path = c.paths.processed / "static.json"
    s = json.loads(path.read_text()) if path.exists() else {}
    for k in ("z_model_hyps", "z_model_api"):
        if s.get(k) is not None:
            return float(s[k])
    log.warning("no model terrain height on file; lapse correction disabled (run `gnostiq pull --only static`)")
    return float(c.site.elev)
