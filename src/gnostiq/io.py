"""Cached downloads."""

import logging
import time
from pathlib import Path

import requests

log = logging.getLogger("gnostiq")
UA = {"User-Agent": "gnostiq/0.1"}


class Missing(Exception):
    pass


def fetch(url, path, params=None, max_age=None, tries=4, timeout=600):
    path = Path(path)
    if path.exists() and (max_age is None or time.time() - path.stat().st_mtime < max_age):
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    err = None
    for i in range(tries):
        try:
            r = requests.get(url, params=params, headers=UA, timeout=timeout)
        except requests.RequestException as e:
            err = e
        else:
            if r.status_code in (400, 404):
                raise Missing(f"{r.status_code} {r.url}: {r.text[:300]}")
            if r.ok:
                tmp = path.with_name(path.name + ".part")
                tmp.write_bytes(r.content)
                tmp.replace(path)
                return path
            err = requests.HTTPError(f"{r.status_code} {r.url}: {r.text[:200]}")
        if i < tries - 1:
            wait = 20 * 2**i
            log.warning("fetch failed (%s); retry in %ss", err, wait)
            time.sleep(wait)
    if path.exists():
        log.warning("using stale %s: %s", path.name, err)
        return path
    raise err
