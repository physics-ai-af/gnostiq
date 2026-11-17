# gnostiq

A correction layer for global weather model forecasts at one site: Jos, Nigeria. It takes the ECMWF forecast for the grid cell over Jos, corrects it for the plateau and puts an uncertainty range on it. The result is then checked against station observations from a wet season the model never saw, next to the standard baselines.

Nothing here has been run on real data yet. The tests use synthetic files written in the real on-disk formats. They show the code works, not that the forecasts are any good.





## Files

Paths are relative to the repo root.

| Path | Purpose |
|---|---|
| `pyproject.toml`  | Package metadata, dependencies, ruff and pytest settings |
| `.python-version`  | Python version uv installs |
| `.gitignore`  | Keeps data/, the virtualenv and caches out of git |
| `.github/workflows/ci.yml`  | GitHub Actions: lint and tests on every push and pull request |
| `gnostiq.toml`  | Run configuration: site, windows, truth sources, models, thresholds |
| `README.md`  | This file |
| `src/gnostiq/__init__.py`  | Package marker (empty) |
| `src/gnostiq/cfg.py`  | Loads and validates gnostiq.toml |
| `src/gnostiq/io.py`  | Cached HTTP downloads with retries |

## Tests

Depending on your project's dependency manager or workflow tool, use the corresponding command:

### Standard Python (`venv` / `virtualenv`)
```
pytest                           # everything (if venv is active)
python -m pytest                 # everything (explicit interpreter)
pytest tests/test_io.py          # one file
```

```
uv run pytest                    # everything
uv run pytest tests/test_io.py   # one file
```

### Poetry
```
poetry run pytest                # everything
poetry run pytest tests/test_io.py # one file
```

### Pipenv
```
pipenv run pytest                # everything
pipenv run pytest tests/test_io.py # one file
```

### Hatch
```
hatch run pytest                 # everything
hatch run pytest tests/test_io.py # one file
```

### PDM
```
pdm run pytest                   # everything
pdm run pytest tests/test_io.py  # one file
```

No test touches the network. Downloads are replaced with stand-ins, and anything that needs data uses synthetic files written in the real formats.

| Path  | What it checks |
|---|---|
| `tests/conftest.py` |Shared fixtures: config writer, and from later branches the staged synthetic data |
| `tests/test_cfg.py`  | Config loading, lookup order, and every validation rule |
| `tests/test_io.py` | Caching, refresh by age, retries, missing files, fallback to a stale copy |



## Configuration

Everything that describes the run lives in `gnostiq.toml` at the repo root. Code never hard-codes the site, the dates or the model.

| Key | Default | Notes |
|---|---|---|
| `site.lat`, `lon`, `elev_m` | 9.8667, 8.9, 1295 | Provisional. Two coordinate sets circulate for this station, about 25 km apart. |
| `site.wmo`, `icao` | 65134, DNJO | The synoptic station and the airport |
| `site.ghcnh` | empty | NOAA station id. Empty means look it up from the WMO number. |
| `site.bbox` | 9.4 to 10.1 N, 8.6 to 9.2 E | Search box for station records |
| `window.start` | 2021-01-01 | Start of the observation record |
| `window.train_end`, `test_start`, `test_end` | 2026-03-31, 2026-04-01, 2026-10-31 | The test window is the 2026 wet season. It must never overlap training. |
| `truth.temp` | `merged` | `ghcnh`, `iem`, or `merged` (station first, METAR fills gaps) |
| `truth.rain` | `chirps` | `station` or `chirps` |
| `truth.chirps_flavor` | `sat` | `sat` or `rnl` |
| `nwp.base` | `ecmwf_ifs025` | The model being corrected |
| `nwp.extra` | GFS, ICON | Scored raw, for comparison only |
| `nwp.start` | 2024-01-01 | Where the forecast archive begins |
| `forecast.lead_days` | 1 to 7 | |
| `forecast.wet_mm`, `heavy_mm` | 1, 10 | Rain thresholds |
| `model.*` | 3 seeds, 64 hidden units | Small on purpose |
| `paths.data` | `data` | Relative to the config file. Git ignores it. |

The file is found by walking up from the working directory, or through the `GNOSTIQ_CFG` environment variable. `cfg.load()` validates it and reports every problem in one error, so you fix the file once rather than once per mistake.

In code:

```python
from gnostiq import cfg

c = cfg.get()  # loaded once per process
c.site.lat, c.window.test_start, c.paths.raw
```

## Downloads

`gnostiq.io.fetch(url, path)` is the one place that talks to the network for plain files. It writes to `path` and never downloads the same file twice unless you give it a `max_age`. A 400 or 404 raises `io.Missing` straight away, since retrying will not make a missing file appear. Anything else is retried with a growing pause, and if a refresh fails but an older copy is on disk, the older copy is used with a warning.
