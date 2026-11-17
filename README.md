# gnostiq

A correction layer for global weather model forecasts at one site: Jos, Nigeria. It takes the ECMWF forecast for the grid cell over Jos, corrects it for the plateau and puts an uncertainty range on it. The result is then checked against station observations from a wet season the model never saw, next to the standard baselines.

Nothing here has been run on real data yet. The tests use synthetic files written in the real on-disk formats. They show the code works, not that the forecasts are any good.

## Tests

Use the block for your tool.

### Standard Python (`venv` / `virtualenv`)

```
pytest                   # everything
python -m pytest         # everything, explicit interpreter
pytest tests/test_qc.py  # one file
```

### uv

```
uv run pytest                   # everything
uv run pytest tests/test_qc.py  # one file
```

### Poetry

```
poetry run pytest                   # everything
poetry run pytest tests/test_qc.py  # one file
```

### Pipenv

```
pipenv run pytest                   # everything
pipenv run pytest tests/test_qc.py  # one file
```

### Hatch

```
hatch run pytest                   # everything
hatch run pytest tests/test_qc.py  # one file
```

### PDM

```
pdm run pytest                   # everything
pdm run pytest tests/test_qc.py  # one file
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
| `tests/test_nwp.py` | Parsing a real response, chunking, request contents, refused groups, assembly, live fallback |
| `tests/test_physics.py` | Formulas against known values, the terrain prior, wind sign, rain-day boundaries, fallbacks |
| `tests/test_precip.py` | File paths, pixel reads, nodata, incremental pulls, preliminary to final, refused days |
| `tests/test_static.py` | Terrain tile naming, model height from pressure, caching, the fallback order |
| `tests/test_qc.py` | Each check on cases it must catch and cases it must leave alone; the full run |

## Setup

You need Python 3.12 or newer. There are no API keys and no accounts. Each block below installs the libraries the code needs, plus pytest and ruff, then runs the tests and the linter.

### Standard Python (`venv` / `virtualenv`)

```
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

```
uv sync
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

`uv sync` reads `pyproject.toml`, creates `.venv` and installs the dev group by default.

### Poetry

```
poetry install
poetry run pytest
poetry run ruff check . && poetry run ruff format --check .
```

Poetry reads the standard `[project]` and `[dependency-groups]` tables, so there is no `[tool.poetry]` section to keep in step. Tested with Poetry 2.4.3. Poetry 1.x does not read `[project]` and will not work. Poetry keeps its environments outside the project unless you run `poetry config virtualenvs.in-project true` first.

### Pipenv

```
pipenv install --dev
pipenv run pytest
pipenv run ruff check . && pipenv run ruff format --check .
```

Pipenv does not read `pyproject.toml`. It reads the `Pipfile`, which carries the same pins as the requirements files and installs the project itself as an editable package. Tested with Pipenv 2026.11.0. Set `PIPENV_VENV_IN_PROJECT=1` if you want the environment in `.venv`.

### Hatch

```
hatch env create
hatch run pytest
hatch run ruff check . && hatch run ruff format --check .
```

`pyproject.toml` has a `[tool.hatch.envs.default]` section with `dependency-groups = ["dev"]`. Without it Hatch's environment has no pytest, and `hatch run pytest` quietly runs whatever pytest is on your `PATH` instead, which then cannot import `gnostiq`. Tested with Hatch 1.18.2. Hatch keeps its environments outside the project; `hatch env find` prints where.

### PDM

```
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

```
gnostiq pull   # download both into data/raw/station/
gnostiq build  # parse and merge into data/interim/
```

### uv

```
uv run gnostiq pull   # download both into data/raw/station/
uv run gnostiq build  # parse and merge into data/interim/
```

### Poetry

```
poetry run gnostiq pull   # download both into data/raw/station/
poetry run gnostiq build  # parse and merge into data/interim/
```

### Pipenv

```
pipenv run gnostiq pull   # download both into data/raw/station/
pipenv run gnostiq build  # parse and merge into data/interim/
```

### Hatch

```
hatch run gnostiq pull   # download both into data/raw/station/
hatch run gnostiq build  # parse and merge into data/interim/
```

### PDM

```
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

```
python scripts/gate.py              # looks the station up by WMO number
python scripts/gate.py NIM00065134  # or name the GHCNh record yourself
```

### uv

```
uv run python scripts/gate.py              # looks the station up by WMO number
uv run python scripts/gate.py NIM00065134  # or name the GHCNh record yourself
```

### Poetry

```
poetry run python scripts/gate.py              # looks the station up by WMO number
poetry run python scripts/gate.py NIM00065134  # or name the GHCNh record yourself
```

### Pipenv

```
pipenv run python scripts/gate.py              # looks the station up by WMO number
pipenv run python scripts/gate.py NIM00065134  # or name the GHCNh record yourself
```

### Hatch

```
hatch run python scripts/gate.py              # looks the station up by WMO number
hatch run python scripts/gate.py NIM00065134  # or name the GHCNh record yourself
```

### PDM

```
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

## Forecast archive

Past forecasts for the Jos grid cell, from Open-Meteo's Previous Runs API. For every hour it gives the value that was forecast one day earlier, two days earlier, and so on up to seven. That is what makes it possible to train and score by lead time without storing every model run.

### Standard Python (`venv` / `virtualenv`)

```
gnostiq pull --only nwp
gnostiq build
```

### uv

```
uv run gnostiq pull --only nwp
uv run gnostiq build
```

### Poetry

```
poetry run gnostiq pull --only nwp
poetry run gnostiq build
```

### Pipenv

```
pipenv run gnostiq pull --only nwp
pipenv run gnostiq build
```

### Hatch

```
hatch run gnostiq pull --only nwp
hatch run gnostiq build
```

### PDM

```
pdm run gnostiq pull --only nwp
pdm run gnostiq build
```

`pull` asks for 92-day chunks and keeps each as a JSON file under `data/raw/nwp/<model>/`. `build` turns them into `data/interim/nwp_<model>.parquet`, one row per valid hour and lead day, with short column names (`f_t2m`, `f_td2m`, `f_tp`, `f_msl`, `f_sp`, `f_cloud`, `f_wspd`, `f_wdir`, and more where the archive has them).

Three details that matter:

- Requests pass `elevation=nan`. Without it Open-Meteo adjusts temperature to a fine terrain model, and the "raw" forecast would no longer be raw.
- Variables are requested in three groups (`core`, `column`, `levels`). If the archive refuses a group, a `<group>.missing` marker is written and the group is not asked for again until you pass `--refresh`. Only a refusal of the base model's core group stops the pull.
- The extra models are only ever scored as raw baselines, so only their core group is fetched.

### What the live archive actually serves

Checked by hand in a browser on 2026-11-17:

| Request | Result |
|---|---|
| `ecmwf_ifs025`, core variables | Works. Lead days 1 and 7 both filled. Grid cell centre 9.75 N 9.0 E, height 1182 m. |
| `ecmwf_ifs025`, CAPE and column water vapour | Served, but every value is null |
| `ecmwf_ifs025`, pressure-level fields | Refused with a 400. Expect one warning on the first pull. |
| `gfs_seamless` | Works, including CAPE |
| `icon_seamless` | Works at short leads. Lead day 7 is null. |

So for the base model the usable inputs are the core set plus shortwave radiation. The code copes with that without special cases: empty columns are simply not used.

`nwp.live(c)` fetches the newest run from the ordinary forecast API. The live-forecast branch uses it later.

The free Open-Meteo API is for non-commercial use and needs attribution.

## Physics

`src/gnostiq/physics.py` holds the meteorology that both training and the live forecast rely on. It has no I/O. There is nothing to run here; the later branches call it.

- `es`, `rh`: saturation vapour pressure and relative humidity (Bolton 1980).
- `height`: how high a pressure surface sits, from the hypsometric equation. Fed the model's own surface and sea-level pressure, it recovers the height of the model grid cell: 1182 m for the cell over Jos, which matches what Open-Meteo reports.
- `lapse`: the lapse rate of the model's 850 to 700 hPa layer, limited to 3 to 9.8 K/km. With no pressure-level data it returns the standard 6.5 K/km.
- `cos_zenith`: where the sun is.
- `pw_from_td`: precipitable water estimated from surface dewpoint (Reitan 1963), for when the model's column water vapour is missing.
- `hourly_features`: adds the terrain-corrected temperature and dewpoint (`t_prior`, `td_prior`, `dep_prior`) and the derived predictors to a table of hourly forecasts.
- `daily_features`: rolls hourly rows up into rain days.

Two conventions are easy to get wrong and are pinned by tests:

- Open-Meteo's precipitation at time `t` fell in the hour before `t`. A rain day starting at `s` therefore sums the hours in `(s, s + 24h]`. Rain reported at 00:00 belongs to the day that just ended.
- The north-easterly wind component `ne` is positive when the wind blows from the north-east, which is Harmattan flow off the Sahara.

A day with any missing hour is dropped rather than summed short.

## Rain truth and terrain

### CHIRPS

When the station gauge is not usable, daily rain truth comes from CHIRPS v3. The daily files are global GeoTIFFs of 10 to 15 MB each, so downloading them whole is out of the question. Instead `precip.py` opens each one over HTTP and reads only the 3 by 3 block of pixels around the station, about 15 km across. It keeps the centre pixel and the block mean; the block mean is what is used as truth.

#### Standard Python (`venv` / `virtualenv`)

```
gnostiq pull --only precip
```

#### uv

```
uv run gnostiq pull --only precip
```

#### Poetry

```
poetry run gnostiq pull --only precip
```

#### Pipenv

```
pipenv run gnostiq pull --only precip
```

#### Hatch

```
hatch run gnostiq pull --only precip
```

#### PDM

```
pdm run gnostiq pull --only precip
```

The series is kept in `data/raw/chirps/chirps_<flavor>.parquet` with columns `day`, `pt`, `tp24`, `stage`.

- `truth.chirps_flavor = "sat"` takes its day-to-day timing from IMERG satellite estimates, `"rnl"` from ERA5. `sat` is the default because ERA5 is itself an ECMWF product, and scoring an ECMWF forecast against ECMWF-timed rain would flatter it.
- Recent days come from the preliminary product until the final one is published, around the third week of the following month. Preliminary days are read again on every pull and replaced when the final file appears.
- The server rate-limits. One test request came back with a 429. A day it refuses is not stored, so the next pull tries it again. Re-run until the log says `0 not read`. The first full pull is about 2,100 small reads and can take 20 to 60 minutes.

On a plain `gnostiq pull`, CHIRPS is skipped when `truth.rain = "station"`. Name it with `--only precip` to fetch it anyway.

File paths were checked against the server's directory listing on 2026-11-17. Final `sat` files existed through October 2026.

CHIRPS daily totals are treated as running 00 to 00 UTC. That is an assumption to check against a few known storm dates.

### Terrain

#### Standard Python (`venv` / `virtualenv`)

```
gnostiq pull --only static
```

#### uv

```
uv run gnostiq pull --only static
```

#### Poetry

```
poetry run gnostiq pull --only static
```

#### Pipenv

```
pipenv run gnostiq pull --only static
```

#### Hatch

```
hatch run gnostiq pull --only static
```

#### PDM

```
pdm run gnostiq pull --only static
```

writes `data/processed/static.json`:

| Key | Meaning |
|---|---|
| `z_station` | Station height from the config |
| `z_model_hyps` | Height of the model grid cell, worked out from the model's own surface and sea-level pressure |
| `z_model_api` | The elevation Open-Meteo reports for the cell |
| `z_dem_point`, `z_dem_9km` | Copernicus 30 m terrain at the station, and averaged over about 9 km |

The correction for terrain is driven by station height minus model height. `static.z_model()` prefers the pressure-derived figure, then the API's. If neither is on file it falls back to the station height, which switches the correction off and logs a warning. A failed terrain download does not stop the pull; the DEM figures are for the gate and for your own checking, not for the model.

## Quality control

Station reports are checked before anything is trained or scored against them. A value that fails a check is removed. Nothing is repaired or interpolated.

### Standard Python (`venv` / `virtualenv`)

```
gnostiq build
```

### uv

```
uv run gnostiq build
```

### Poetry

```
poetry run gnostiq build
```

### Pipenv

```
pipenv run gnostiq build
```

### Hatch

```
hatch run gnostiq build
```

### PDM

```
pdm run gnostiq build
```

now also writes `data/interim/obs.parquet` (`valid`, `t`, `td`, `src`) and a tally in `data/reports/qc.md`.

| Check | Rule |
|---|---|
| Range | Temperature within -10 to 50 degC, dewpoint within -40 to 35 degC |
| Dewpoint above temperature | Up to 0.5 degC over is rounding and is set equal to temperature. More than that is a bad report and the dewpoint is dropped. |
| Spike | More than 8 degC away from both neighbours, in the same direction, with both neighbours within 3 hours |
| Flatline | 12 or more identical readings in a row spanning at least 24 hours |
| Climatological outlier | Further from the median for that month and hour than the larger of 8 degC and six robust standard deviations, where there are at least 10 readings to judge by |

A dewpoint with no temperature beside it is dropped too, since it cannot be checked.

The rules are deliberately loose. A real cold front is a large jump that persists, so it is not a spike. Whole-degree METAR temperatures repeat for hours on a calm night, so a short run of identical values is not a flatline. Both cases have tests.

Read `data/reports/qc.md` after the first real build. A check that removes hundreds of values is telling you something about the station or about the check.
