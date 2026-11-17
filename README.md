# gnostiq

A correction layer for global weather model forecasts at one site: Jos, Nigeria. It takes the ECMWF forecast for the grid cell over Jos, corrects it for the plateau and puts an uncertainty range on it. The result is then checked against station observations from a wet season the model never saw, next to the standard baselines.

Nothing here has been run on real data yet. The tests use synthetic files written in the real on-disk formats. They show the code works, not that the forecasts are any good.

## Files

Paths are relative to the repo root.

| Path | Purpose |
|---|---|
| `pyproject.toml` | Package metadata, dependencies, ruff and pytest settings |
| `.python-version` | Python version uv installs |
| `.gitignore` | Keeps data/, the virtualenv and caches out of git |
| `.github/workflows/ci.yml` | GitHub Actions: lint and tests on every push and pull request |
| `gnostiq.toml` | Run configuration: site, windows, truth sources, models, thresholds |
| `README.md` | This file |
| `src/gnostiq/__init__.py` | Package marker (empty) |
| `src/gnostiq/cfg.py` | Loads and validates gnostiq.toml |
| `src/gnostiq/io.py` | Cached HTTP downloads with retries |
| `src/gnostiq/ingest/__init__.py` | Package marker (empty) |
| `src/gnostiq/ingest/station.py` | NOAA GHCNh and IEM METAR download, parsing, merge, daily rain totals |
| `src/gnostiq/cli.py` | The `gnostiq` command |

## Tests

Depending on your project's dependency manager or workflow tool, use the corresponding command:

### Standard Python (`venv` / `virtualenv`)
```bash
pytest                           # everything (if venv is active)
python -m pytest                 # everything (explicit interpreter)
pytest tests/test_cli.py         # one file
```

### uv
```bash
uv run pytest                    # everything
uv run pytest tests/test_cli.py  # one file
```

### Poetry
```bash
poetry run pytest                # everything
poetry run pytest tests/test_cli.py # one file
```

### Pipenv
```bash
pipenv run pytest                # everything
pipenv run pytest tests/test_cli.py # one file
```

### Hatch
```bash
hatch run pytest                 # everything
hatch run pytest tests/test_cli.py # one file
```

### PDM
```bash
pdm run pytest                   # everything
pdm run pytest tests/test_cli.py # one file
```

No test touches the network. Downloads are replaced with stand-ins, and anything that needs data uses synthetic files written in the real formats.

| Path | What it checks |
|---|---|
| `tests/conftest.py` | Shared fixtures: config writer, and from later branches the staged synthetic data |
| `tests/test_cfg.py` | Config loading, lookup order, and every validation rule |
| `tests/test_io.py` | Caching, refresh by age, retries, missing files, fallback to a stale copy |
| `tests/synth.py` | Synthetic raw files in the real formats, used by the fixtures |
| `tests/test_station.py` | Parsing both sources, NOAA quality flags, trace rain, rain-day rules, station lookup, merge modes |
| `tests/test_cli.py` | Argument handling, unknown sources, data directories, helpful errors |

## Setup

You need Python 3.12 or newer. There are no API keys and no accounts. Depending on your project's dependency manager or workflow tool, use the corresponding setup commands:

### Standard Python (`venv` / `virtualenv`)
```bash
python -m venv .venv
source .venv/bin/activate                          # On Windows: .venv\Scripts\activate
pip install -e .
pytest
ruff check . && ruff format --check .
```

### uv
```bash
uv sync
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

`uv sync` creates `.venv` and a `uv.lock`. Leave the lock file uncommitted while you work through the stack, because most branches add a dependency. Once the last branch is merged, run `uv lock` and commit it.

### Poetry
```bash
poetry install
poetry run pytest
poetry run ruff check . && poetry run ruff format --check .
```

### Pipenv
```bash
pipenv install --dev
pipenv run pytest
pipenv run ruff check . && pipenv run ruff format --check .
```

### Hatch
```bash
hatch env create
hatch run pytest
hatch run ruff check . && hatch run ruff format --check .
```

### PDM
```bash
pdm install
pdm run pytest
pdm run ruff check . && pdm run ruff format --check .
```

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

## Station observations

Two sources of observed weather at Jos:

- **NOAA GHCNh**: the full record of the synoptic station (WMO 65134), one pipe-separated file.
- **Iowa Environmental Mesonet**: METAR reports from the airport (DNJO), one CSV per year.

Depending on your project's dependency manager or workflow tool, run the ingestion pipeline using:

### Standard Python (`venv` / `virtualenv`)
```bash
gnostiq pull     # download both into data/raw/station/
gnostiq build    # parse and merge into data/interim/
```

### uv
```bash
uv run gnostiq pull     # download both into data/raw/station/
uv run gnostiq build    # parse and merge into data/interim/
```

### Poetry
```bash
poetry run gnostiq pull     # download both into data/raw/station/
poetry run gnostiq build    # parse and merge into data/interim/
```

### Pipenv
```bash
pipenv run gnostiq pull     # download both into data/raw/station/
pipenv run gnostiq build    # parse and merge into data/interim/
```

### Hatch
```bash
hatch run gnostiq pull     # download both into data/raw/station/
hatch run gnostiq build    # parse and merge into data/interim/
```

### PDM
```bash
pdm run gnostiq pull     # download both into data/raw/station/
pdm run gnostiq build    # parse and merge into data/interim/
```

`pull` skips anything already on disk. `pull --refresh` re-downloads the files that grow: the station record and the current year's METARs.

`build` writes two tables:

| File | Contents |
|---|---|
| `data/interim/station.parquet` | One row per hour: `valid` (UTC), `t`, `td`, `ps`, `slp`, `qnh`, `wspd`, `p6`, `p12`, `p24`, and `src` saying which source the row came from |
| `data/interim/station_rain.parquet` | 24 h rain totals for days running 06 to 06 UTC, labelled by the start date |

How the merge works: `truth.temp` in the config picks `ghcnh`, `iem`, or `merged`. With `merged`, the station value wins where both exist and the METAR fills the gaps. Reports within ten minutes of the hour are snapped to that hour. Half-hourly METARs are dropped, since counting them against the wrong hour would be worse than not having them.

A daily rain total is taken from the 24 h report at the closing 06 UTC. Failing that it is built from two 12 h reports, then from four 6 h reports. If any piece is missing there is no total for that day; a partial sum is never passed off as a daily one.

### Not yet checked against a real file

NOAA serves these files as downloads only, so the parser is written from NOAA's documentation and has not seen a real file. If `build` reports zero observations or a missing column, open the header of `data/raw/station/GHCNh_*.psv` and compare it with three things in `src/gnostiq/ingest/station.py`:

- `COLS`: the column names (`temperature`, `dew_point_temperature`, `precipitation_6_hour` and so on)
- `GOOD_QC`: the quality codes that count as passed. Anything else is dropped.
- the trace-rain rule: a missing amount with `T` in its measurement code is read as zero

The station list is parsed loosely on purpose: id, latitude, longitude and elevation first, then whatever follows. A layout change in the later columns will not break the lookup.