"""TAMSAT v3.1 daily rain at the site: a second satellite truth to score rain against."""

import logging
import time
import warnings

import pandas as pd
import rasterio
from rasterio.errors import NotGeoreferencedWarning, RasterioIOError

from gnostiq.ingest import precip
from gnostiq.io import Missing, fetch

log = logging.getLogger("gnostiq")

BASE = "https://gws-access.jasmin.ac.uk/public/tamsat/rfe/data/v3.1/daily"
PAUSE = 0.5
LAG = 10  # days; files appear every five days


def url(day):
    return f"{BASE}/{day.year}/{day.month:02d}/rfe{day.year}_{day.month:02d}_{day.day:02d}.v3.1.nc"


def cache(c):
    return c.paths.raw / "tamsat" / "tamsat.parquet"


def read(path, lat, lon):
    # the container itself has no grid, only its variables do
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", NotGeoreferencedWarning)
        with rasterio.open(path) as ds:
            subs = ds.subdatasets
    # rfe_filled patches gaps with climatology, which is no truth
    src = next((s for s in subs if s.endswith(":rfe")), str(path))
    return precip.read_cell(src, lat, lon)


def pull(c, refresh=False):
    path = cache(c)
    have = pd.read_parquet(path) if path.exists() else pd.DataFrame(columns=["day", "pt", "tp24", "stage"])
    today = pd.Timestamp.now("UTC").tz_localize(None).floor("D")
    # only scored days: about 1 MB a file for all of Africa
    end = min(today - pd.Timedelta(days=LAG), pd.Timestamp(c.window.test_end))
    todo = pd.date_range(c.window.test_start, end, freq="D").difference(pd.DatetimeIndex(have.day))
    if len(todo) == 0:
        return have
    log.info("tamsat: reading %d days", len(todo))
    tmp = path.parent / "day.nc"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for n, day in enumerate(todo, 1):
        try:
            fetch(url(day), tmp, timeout=120)
            pt, box = read(tmp, c.site.lat, c.site.lon)
        except (Missing, RasterioIOError) as e:
            log.warning("tamsat %s: %s", day.date(), e)
        else:
            rows.append({"day": day, "pt": pt, "tp24": box, "stage": "final"})
        finally:
            tmp.unlink(missing_ok=True)
        if n % 50 == 0:
            log.info("tamsat: %d/%d", n, len(todo))
            precip.save(path, have, rows)
        time.sleep(PAUSE)
    out = precip.save(path, have, rows)
    log.info("tamsat: %d days on file, %d not read (re-run to retry)", len(out), len(todo) - len(rows))
    return out
