# gnostiq

A correction layer for global weather model forecasts at one site: Jos, Nigeria. It takes the ECMWF forecast for the grid cell over Jos, corrects it for the plateau and puts an uncertainty range on it. The result is then checked against station observations from a wet season the model never saw, next to the standard baselines.

Nothing here has been run on real data yet. The tests use synthetic files written in the real on-disk formats. They show the code works, not that the forecasts are any good.

## Tests

Use the block for your tool.

### Standard Python (`venv` / `virtualenv`)

```bash
pytest                     # everything
python -m pytest           # everything, explicit interpreter
pytest tests/test_gate.py  # one file
```

### uv

```bash
uv run pytest                     # everything
uv run pytest tests/test_gate.py  # one file
```

### Poetry

```bash
poetry run pytest                     # everything
poetry run pytest tests/test_gate.py  # one file
```

### Pipenv

```bash
pipenv run pytest                     # everything
pipenv run pytest tests/test_gate.py  # one file
```

### Hatch

```bash
hatch run pytest                     # everything
hatch run pytest tests/test_gate.py  # one file
```

### PDM

```bash
pdm run pytest                     # everything
pdm run pytest tests/test_gate.py  # one file
```

No test touches the network. Downloads are replaced with stand-ins, and anything that needs data uses synthetic files written in the real formats.

| Path | What it checks |
|---|---|
| `tests/conftest.py` | Shared fixtures: config writer, and from later branches the staged synthetic data |
| `tests/test_cfg.py` | Config loading, lookup order, and every validation rule |
| `tests/test_io.py` | Caching, refresh by age, retries, missing files, fallback to a stale copy |
| `tests/test_requirements.py` | requirements files and Pipfile match pyproject.toml, with pins inside its ranges |
| `tests/synth.py` | Synthetic raw files in the real formats, used by the fixtures |
| `tests/test_station.py` | Parsing both sources, NOAA quality flags, trace rain, rain-day rules, station lookup, merge modes |
| `tests/test_cli.py` | Argument handling, unknown sources, data directories, helpful errors |
| `tests/test_gate.py` | Runs the script on a good record, a pinned id, a daytime-only station and an empty lookup |

## Setup

You need Python 3.12 or newer. There are no API keys and no accounts. Each block below installs the libraries the code needs, plus pytest and ruff, then runs the tests and the linter.

### Standard Python (`venv` / `virtualenv`)

```bash
python -m venv .venv                   # or: virtualenv .venv
source .venv/bin/activate              # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
pip install -e . --no-deps
pytest
ruff check . && ruff format --check .
```

| File | Holds |
|---|---|
| `requirements.txt` | What the code needs to run, pinned to the versions the tests passed with |
| `requirements-dev.txt` | `-r requirements.txt` plus pytest and ruff (and httpx from `15-api-web` on) |

The second `pip install` puts the `gnostiq` package itself into the environment, which gives you the `gnostiq` command. `--no-deps` stops pip from re-resolving what the requirements file already pinned. A bare `pip install -e .` would skip pytest and ruff, which live in a dependency group pip only reads with `--group dev` on pip 25.1 or newer.

The requirements files list direct dependencies only, so pip still picks versions for the packages those pull in.

### uv

```bash
uv sync
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

`uv sync` reads `pyproject.toml`, creates `.venv` and installs the dev group by default.

### Poetry

```bash
poetry install
poetry run pytest
poetry run ruff check . && poetry run ruff format --check .
```

Poetry reads the standard `[project]` and `[dependency-groups]` tables, so there is no `[tool.poetry]` section to keep in step. Tested with Poetry 2.4.3. Poetry 1.x does not read `[project]` and will not work. Poetry keeps its environments outside the project unless you run `poetry config virtualenvs.in-project true` first.

### Pipenv

```bash
pipenv install --dev
pipenv run pytest
pipenv run ruff check . && pipenv run ruff format --check .
```

Pipenv does not read `pyproject.toml`. It reads the `Pipfile`, which carries the same pins as the requirements files and installs the project itself as an editable package. Tested with Pipenv 2026.11.0. Set `PIPENV_VENV_IN_PROJECT=1` if you want the environment in `.venv`.

### Hatch

```bash
hatch env create
hatch run pytest
hatch run ruff check . && hatch run ruff format --check .
```

`pyproject.toml` has a `[tool.hatch.envs.default]` section with `dependency-groups = ["dev"]`. Without it Hatch's environment has no pytest, and `hatch run pytest` quietly runs whatever pytest is on your `PATH` instead, which then cannot import `gnostiq`. Tested with Hatch 1.18.2. Hatch keeps its environments outside the project; `hatch env find` prints where.

### PDM

```bash
pdm install
pdm run pytest
pdm run ruff check . && pdm run ruff format --check .
```

PDM reads `pyproject.toml` as is, creates `.venv`, and installs the dev group by default. Tested with PDM 2.29.7. It also writes `.pdm-python`, a local file that git ignores.

### Lock files

Every tool except plain pip writes its own lock file: `uv.lock`, `poetry.lock`, `Pipfile.lock` or `pdm.lock`. None is committed, because most branches add a dependency. Once the last branch is merged, pick the tool you will keep using, run its lock or install command, and commit that one file.

### Adding a dependency

Add it to `pyproject.toml`. Then add the same pin to `requirements.txt` (or `requirements-dev.txt` for a dev tool) and to the `Pipfile`. `tests/test_requirements.py` fails if the three disagree.

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

Run the ingestion with the block for your tool:

### Standard Python (`venv` / `virtualenv`)

```bash
gnostiq pull   # download both into data/raw/station/
gnostiq build  # parse and merge into data/interim/
```

### uv

```bash
uv run gnostiq pull   # download both into data/raw/station/
uv run gnostiq build  # parse and merge into data/interim/
```

### Poetry

```bash
poetry run gnostiq pull   # download both into data/raw/station/
poetry run gnostiq build  # parse and merge into data/interim/
```

### Pipenv

```bash
pipenv run gnostiq pull   # download both into data/raw/station/
pipenv run gnostiq build  # parse and merge into data/interim/
```

### Hatch

```bash
hatch run gnostiq pull   # download both into data/raw/station/
hatch run gnostiq build  # parse and merge into data/interim/
```

### PDM

```bash
pdm run gnostiq pull   # download both into data/raw/station/
pdm run gnostiq build  # parse and merge into data/interim/
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

## Station data gate

Run this before any modelling. It answers one question: is the Jos record good enough to be the truth the forecasts are judged against?

### Standard Python (`venv` / `virtualenv`)

```bash
python scripts/gate.py              # looks the station up by WMO number
python scripts/gate.py NIM00065134  # or name the GHCNh record yourself
```

### uv

```bash
uv run python scripts/gate.py              # looks the station up by WMO number
uv run python scripts/gate.py NIM00065134  # or name the GHCNh record yourself
```

### Poetry

```bash
poetry run python scripts/gate.py              # looks the station up by WMO number
poetry run python scripts/gate.py NIM00065134  # or name the GHCNh record yourself
```

### Pipenv

```bash
pipenv run python scripts/gate.py              # looks the station up by WMO number
pipenv run python scripts/gate.py NIM00065134  # or name the GHCNh record yourself
```

### Hatch

```bash
hatch run python scripts/gate.py              # looks the station up by WMO number
hatch run python scripts/gate.py NIM00065134  # or name the GHCNh record yourself
```

### PDM

```bash
pdm run python scripts/gate.py              # looks the station up by WMO number
pdm run python scripts/gate.py NIM00065134  # or name the GHCNh record yourself
```

It shares the download cache with `gnostiq pull`, prints a one-line verdict and writes the detail to `data/reports/gate.md`.

| Verdict | Meaning | What to set in `gnostiq.toml` |
|---|---|---|
| PASS | Good for temperature and for rain | `site.ghcnh`, `truth.temp`, `truth.rain = "station"` |
| PARTIAL | Temperature is good, the gauge record is not | `truth.temp`, `truth.rain = "chirps"` |
| FAIL | No source meets the temperature thresholds | Read the hour-of-day table first |

The report ends with the exact lines to paste into the config.

What it measures:

- **Which station this is.** Every distinct latitude, longitude and elevation in the record, with dates. A change part-way through means the station moved. It also works the barometer's height out of the pressure readings, as a check on the listed 1295 m, and compares synoptic temperatures with METAR temperatures at the same hours to see whether they come from one instrument.
- **Temperature and dewpoint.** Monthly coverage of the eight synoptic hours, the share of days with a reading at each hour of the day, how many test-season days have both a pre-dawn and an afternoon reading, and the longest gap.
- **Rain.** How many wet-season days have a usable 24 h total, how many of those are explicit zeros, which hours the accumulation reports arrive at, and annual totals to hold against CHIRPS.

The thresholds are constants at the top of the script. They are working numbers, not a standard. Look at one real report before changing them.

A FAIL is often just a station that does not report at night. That shows up plainly in the hour-of-day table. Such a station can still verify daytime hours with `truth.temp = "merged"`, but then say so wherever you publish scores.
