"""CHIRPS v3 daily rain at the site."""

import logging
import time

import numpy as np
import pandas as pd
import rasterio
from rasterio.errors import RasterioIOError
from rasterio.windows import Window

log = logging.getLogger("gnostiq")

BASE = "https://data.chc.ucsb.edu/products/CHIRPS/v3.0/daily"
GDAL = {
    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
    "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif",
    "CPL_VSIL_CURL_USE_HEAD": "NO",  # one request fewer per file
    "GDAL_HTTP_MAX_RETRY": "5",
    "GDAL_HTTP_RETRY_DELAY": "10",
    "GDAL_HTTP_TIMEOUT": "60",
}
PAUSE = 1.0  # seconds between days; CHC answers 429 to faster readers


def url(day, flavor, stage):
    y, m, d = day.year, day.month, day.day
    if stage == "final":
        return f"{BASE}/final/{flavor}/{y}/chirps-v3.0.{flavor}.{y}.{m:02d}.{d:02d}.tif"
    return f"{BASE}/prelim/sat/{y}/chirps-v3.0.prelim.{y}.{m:02d}.{d:02d}.tif"


def read_cell(src, lat, lon):
    with rasterio.open(src) as ds:
        row, col = ds.index(lon, lat)
        a = ds.read(1, window=Window(col - 1, row - 1, 3, 3)).astype(float)
        nodata = ds.nodata
    if a.shape != (3, 3):
        raise ValueError(f"site falls on the raster edge in {src}")
    a[a < 0] = np.nan
    if nodata is not None:
        a[a == nodata] = np.nan
    return a[1, 1], (np.nanmean(a) if np.isfinite(a).any() else np.nan)


def one(day, lat, lon, flavor):
    for stage in ("final", "prelim"):
        try:
            pt, box = read_cell("/vsicurl/" + url(day, flavor, stage), lat, lon)
        except RasterioIOError:
            continue
        return {"day": day, "pt": pt, "tp24": box, "stage": stage}
    return None


def cache(c):
    return c.paths.raw / "chirps" / f"chirps_{c.truth.chirps_flavor}.parquet"


def pull(c, refresh=False):
    path = cache(c)
    have = pd.read_parquet(path) if path.exists() else pd.DataFrame(columns=["day", "pt", "tp24", "stage"])
    end = pd.Timestamp.now("UTC").tz_localize(None).floor("D") - pd.Timedelta(days=2)
    want = pd.date_range(c.window.start, end, freq="D")
    todo = want.difference(pd.DatetimeIndex(have.day[have.stage == "final"]))
    if len(todo) == 0:
        return have
    # forecast years first, so a stopped run still leaves the model's days on file
    cut = pd.Timestamp(c.nwp.start)
    todo = todo[todo >= cut].append(todo[todo < cut])
    log.info("chirps: reading %d days", len(todo))

    rows = []
    with rasterio.Env(**GDAL):
        for n, day in enumerate(todo, 1):
            r = one(day, c.site.lat, c.site.lon, c.truth.chirps_flavor)
            if r:
                rows.append(r)
            if n % 200 == 0:
                log.info("chirps: %d/%d", n, len(todo))
                save(path, have, rows)
            time.sleep(PAUSE)
    out = save(path, have, rows)
    log.info("chirps: %d days on file, %d not read (re-run to retry)", len(out), len(todo) - len(rows))
    return out


def save(path, have, rows):
    new = pd.DataFrame(rows, columns=["day", "pt", "tp24", "stage"])
    out = pd.concat([have[~have.day.isin(new.day)], new], ignore_index=True) if len(have) else new
    out = out.sort_values("day").reset_index(drop=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Ctrl+C mid-write must not leave a broken cache
    tmp = path.with_name(path.name + ".part")
    out.to_parquet(tmp, index=False)
    tmp.replace(path)
    return out
