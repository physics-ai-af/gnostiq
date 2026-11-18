# gnostiq

A correction layer for global weather model forecasts at one site: Jos, Nigeria. It takes the ECMWF forecast for the grid cell over Jos, corrects it for the plateau and puts an uncertainty range on it. The result is then checked against station observations from a wet season the model never saw, next to the standard baselines.

Nothing here has been run on real data yet. The tests use synthetic files written in the real on-disk formats. They show the code works, not that the forecasts are any good.

## Tests

Use the block for your tool.

### Standard Python (`venv` / `virtualenv`)

```bash
pytest                         # everything
python -m pytest               # everything, explicit interpreter
pytest tests/test_pipeline.py  # one file
```

### uv

```bash
uv run pytest                         # everything
uv run pytest tests/test_pipeline.py  # one file
```

### Poetry

```bash
poetry run pytest                         # everything
poetry run pytest tests/test_pipeline.py  # one file
```

### Pipenv

```bash
pipenv run pytest                         # everything
pipenv run pytest tests/test_pipeline.py  # one file
```

### Hatch

```bash
hatch run pytest                         # everything
hatch run pytest tests/test_pipeline.py  # one file
```

### PDM

```bash
pdm run pytest                         # everything
pdm run pytest tests/test_pipeline.py  # one file
```

No test touches the network. Downloads are replaced with stand-ins, and anything that needs data uses synthetic files written in the real formats.

| Path | What it checks |
|---|---|
| `tests/conftest.py` | Shared fixtures: config writer, and from later branches the staged synthetic data |
| `tests/data/gnostiq.toml` | Frozen copy of the Jos config that the fixtures edit, so changing site leaves the tests alone |
| `tests/test_cfg.py` | Config loading, lookup order, and every validation rule |
| `tests/test_io.py` | Caching, refresh by age, retries, missing files, fallback to a stale copy |
| `tests/test_requirements.py` | requirements files and Pipfile match pyproject.toml, with pins inside its ranges |
| `tests/synth.py` | Synthetic raw files in the real formats, used by the fixtures |
| `tests/test_station.py` | Parsing both sources, NOAA quality flags, trace rain, rain-day rules, station lookup, merge modes |
| `tests/data/GHCNh_NII0000DNJO_excerpt.psv` | Two rows of the real Jos airport record, with its full header |
| `tests/test_cli.py` | Argument handling, unknown sources, data directories, helpful errors |
| `tests/test_gate.py` | Runs the script on a good record, a pinned id, a station away from the site, a daytime-only station and an empty lookup |
| `tests/test_nwp.py` | Parsing a real response, chunking, request contents, refused groups, assembly, live fallback |
| `tests/test_physics.py` | Formulas against known values, the terrain prior, wind sign, rain-day boundaries, fallbacks |
| `tests/test_precip.py` | File paths, pixel reads, nodata, incremental pulls, preliminary to final, refused days |
| `tests/test_static.py` | Terrain tile naming, model height from pressure, caching, the fallback order |
| `tests/test_qc.py` | Each check on cases it must catch and cases it must leave alone; the full run |
| `tests/test_align.py` | Split boundaries, the joins, rain-day sums, truth source selection, missing inputs |
| `tests/test_dist.py` | CRPS against sampling, point forecasts, rain quantiles and exceedance |
| `tests/test_baselines.py` | Each baseline recovers a known signal; no test-window leakage; persistence timing |
| `tests/test_verify.py` | Threat score, bootstrap, reliability bins, common cases, a baseline-only scorecard |
| `tests/test_model.py` | The untrained net returns the prior; constraints hold for random weights; losses; round trip |
| `tests/test_train.py` | Whole-week validation split, early stopping, bundle contents, constraints, the scored model |
| `tests/test_cases.py` | Case selection, ordering, completeness, and the saved file |
| `tests/test_run.py` | Lead-day rounding, coverage, physical consistency, input masking, atomic write |
| `tests/test_api.py` | 404 before reports exist, reports served as written, the page, the method note |
| `tests/test_pipeline.py` | The whole pipeline through the CLI, then the live run and the API |

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
| `requirements-dev.txt` | `-r requirements.txt` plus pytest and ruff (and httpx2, for the API tests, from `15-api-web` on) |

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
| PARTIAL | Temperature is good, the gauge record is not | `site.ghcnh` if the temperature comes from GHCNh, `truth.temp`, `truth.rain = "chirps"` |
| FAIL | No source meets the temperature thresholds | Read the hour-of-day table first |

The report ends with the keys to change, grouped under `[site]` and `[truth]`. Every one already exists in `gnostiq.toml`, so edit the existing lines rather than pasting a second `[site]` table, which TOML rejects.

If the station reports from more than 1 km away from `site.lat`/`site.lon`, or more than 10 m from `site.elev_m`, the report also gives the station's own coordinates. Use them: the forecast grid cell, the CHIRPS cell and the lapse-rate correction are all read at the configured site, so a site 25 km from the instrument verifies the wrong place.

What it measures:

- **Which station this is.** Every distinct latitude, longitude and elevation in the record, with dates. A change part-way through means the station moved. It also works the barometer's height out of the pressure readings, as a check on the listed 1295 m, and compares synoptic temperatures with METAR temperatures at the same hours to see whether they come from one instrument.
- **Temperature and dewpoint.** Monthly coverage of the eight synoptic hours, the share of days with a reading at each hour of the day, how many test-season days have both a pre-dawn and an afternoon reading, and the longest gap.
- **Rain.** How many wet-season days have a usable 24 h total, how many of those are explicit zeros, which hours the accumulation reports arrive at, and annual totals to hold against CHIRPS.

The thresholds are constants at the top of the script. They are working numbers, not a standard. Look at one real report before changing them.

A FAIL is often just a station that does not report at night. That shows up plainly in the hour-of-day table. Such a station can still verify daytime hours with `truth.temp = "merged"`, but then say so wherever you publish scores.

## Forecast archive

Past forecasts for the Jos grid cell, from Open-Meteo's Previous Runs API. For every hour it gives the value that was forecast one day earlier, two days earlier, and so on up to seven. That is what makes it possible to train and score by lead time without storing every model run.

### Standard Python (`venv` / `virtualenv`)

```bash
gnostiq pull --only nwp
gnostiq build
```

### uv

```bash
uv run gnostiq pull --only nwp
uv run gnostiq build
```

### Poetry

```bash
poetry run gnostiq pull --only nwp
poetry run gnostiq build
```

### Pipenv

```bash
pipenv run gnostiq pull --only nwp
pipenv run gnostiq build
```

### Hatch

```bash
hatch run gnostiq pull --only nwp
hatch run gnostiq build
```

### PDM

```bash
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

```bash
gnostiq pull --only precip
```

#### uv

```bash
uv run gnostiq pull --only precip
```

#### Poetry

```bash
poetry run gnostiq pull --only precip
```

#### Pipenv

```bash
pipenv run gnostiq pull --only precip
```

#### Hatch

```bash
hatch run gnostiq pull --only precip
```

#### PDM

```bash
pdm run gnostiq pull --only precip
```

The series is kept in `data/raw/chirps/chirps_<flavor>.parquet` with columns `day`, `pt`, `tp24`, `stage`.

- `truth.chirps_flavor = "sat"` takes its day-to-day timing from IMERG satellite estimates, `"rnl"` from ERA5. `sat` is the default because ERA5 is itself an ECMWF product, and scoring an ECMWF forecast against ECMWF-timed rain would flatter it.
- Recent days come from the preliminary product until the final one is published, around the third week of the following month. Preliminary days are read again on every pull and replaced when the final file appears.
- The server rate-limits, and answers 429 to readers that go too fast. The pull reads one day at a time with a one-second pause, and the days the model trains and tests on (from `nwp.start`) come first, so a stopped run still leaves those on file. A day it refuses is not stored, so the next pull tries it again. Re-run until the log says `0 not read`. It reads only up to the end of the test season, since later days are never scored, and saves every 50 days. The 2021 to 2025 window is about 1,800 reads. Each one is a few round trips to California, so on a slow connection plan on a few hours; a server in Europe or the US gets through it much faster.

On a plain `gnostiq pull`, CHIRPS is skipped when `truth.rain = "station"`. Name it with `--only precip` to fetch it anyway.

File paths were checked against the server's directory listing on 2026-11-17. Final `sat` files existed through October 2026.

CHIRPS daily totals are treated as running 00 to 00 UTC. That is an assumption to check against a few known storm dates.

### Terrain

#### Standard Python (`venv` / `virtualenv`)

```bash
gnostiq pull --only static
```

#### uv

```bash
uv run gnostiq pull --only static
```

#### Poetry

```bash
poetry run gnostiq pull --only static
```

#### Pipenv

```bash
pipenv run gnostiq pull --only static
```

#### Hatch

```bash
hatch run gnostiq pull --only static
```

#### PDM

```bash
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

```bash
gnostiq build
```

### uv

```bash
uv run gnostiq build
```

### Poetry

```bash
poetry run gnostiq build
```

### Pipenv

```bash
pipenv run gnostiq build
```

### Hatch

```bash
hatch run gnostiq build
```

### PDM

```bash
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

## Training tables

`align.py` joins forecasts to observations. It is the last step of `gnostiq build`.

| File | One row per | Holds |
|---|---|---|
| `data/processed/pairs_hourly.parquet` | valid hour and lead day | the forecast columns, the physics features, observed `o_t2m` and `o_td2m`, and `split` |
| `data/processed/pairs_daily.parquet` | rain day and lead day | daily forecast aggregates, the moisture supply `pw`, observed `o_tp24`, and `split` |

`split` is `train` from `nwp.start` to `window.train_end`, `test` inside the test window, and `other` for everything else. Nothing labelled `test` is used for fitting anywhere in the code. `other` covers days after the test window ends: kept, never fitted on, never scored.

Rain days start at 06 UTC when the truth is the station gauge, because that is how synoptic rain is reported, and at 00 UTC when the truth is CHIRPS. The forecast is summed over whichever day the truth uses.

A pair where the observation and the terrain-corrected forecast differ by more than 15 degC is dropped. At that size one of the two is broken, and there is no way to tell which from here.

If either table ends up with no training rows or no test rows, the build stops and says so. That nearly always means the windows in the config do not overlap the data that was pulled.

## Baselines

These are the forecasts the model has to beat. They are built before the model exists, so the bar is fixed first.

### Standard Python (`venv` / `virtualenv`)

```bash
gnostiq baselines
```

### uv

```bash
uv run gnostiq baselines
```

### Poetry

```bash
poetry run gnostiq baselines
```

### Pipenv

```bash
pipenv run gnostiq baselines
```

### Hatch

```bash
hatch run gnostiq baselines
```

### PDM

```bash
pdm run gnostiq baselines
```

| System | Temperature and dewpoint | Rain |
|---|---|---|
| `clim` | Harmonic fit to the station record: annual cycle, daily cycle and their interaction | What fell within 15 days of that calendar date in earlier years |
| `persist` | The observation one lead time earlier | The last complete day's total at the time the forecast was issued |
| `raw` | The model's grid-cell value | The model's 24 h total |
| `lapse` | `raw` moved to station height | not applicable |
| `emos` | Gaussian regression on the terrain-corrected forecast, fitted by minimum CRPS, one fit per lead day | Logistic regression for wet or dry, gamma regression for the amount |
| `raw:<model>` | Each extra model, raw | Same |

`emos` is the one that counts. Beating a raw model that sits 113 m too low proves very little. A method that cannot beat a standard statistical correction has not earned its complexity.

Climatology is fitted only on observations before the test window. Persistence only uses observations that existed when the forecast was issued. Both are tested.

Outputs, both under `data/processed/`:

- `pred_hourly_base.parquet`: `valid`, `lead_day`, `split`, `var`, `obs`, `system`, `mu`, `sigma`. `sigma` is empty for systems that give a single value.
- `pred_daily_base.parquet`: `day`, `lead_day`, `split`, `obs`, `system`, `p1` and `p10` (chance of at least the wet and heavy thresholds), and 99 quantiles `q01` to `q99`.

`dist.py` has the scoring maths these share with the scorecard: CRPS for a normal distribution, CRPS from quantiles, and the rain distribution, which is a point mass at zero plus a gamma above the wet threshold.

## Scorecard

### Standard Python (`venv` / `virtualenv`)

```bash
gnostiq verify  # or: gnostiq all
```

### uv

```bash
uv run gnostiq verify  # or: gnostiq all
```

### Poetry

```bash
poetry run gnostiq verify  # or: gnostiq all
```

### Pipenv

```bash
pipenv run gnostiq verify  # or: gnostiq all
```

### Hatch

```bash
hatch run gnostiq verify  # or: gnostiq all
```

### PDM

```bash
pdm run gnostiq verify  # or: gnostiq all
```

scores every system on the test window and writes `data/reports/scorecard.md` for reading and `scorecard.json` for the web page.

It runs as soon as the baselines exist. Until the model has been trained the card simply has no `gnostiq` row and no skill section. That is deliberate: you can look at how good the baselines are before you have anything to compare them with.

How it keeps the comparison fair:

- **Same cases for everyone.** A case counts only if every core system produced a forecast for it. The extra models can lack cases (ICON has no day 7); their smaller `n` is shown and they are not directly comparable.
- **Proper scores.** CRPS for all three variables, Brier score at the wet and heavy thresholds. For a system that gives a single number, CRPS is the absolute error, so point forecasts and probabilistic ones sit in one column.
- **Honest intervals.** Skill is `1 - score / reference score`. Its 95% interval comes from resampling whole days 1,000 times, because errors within one day are not independent. An interval that includes zero is not evidence of skill, and the report says so at the top.

Also reported: bias, mean absolute error, how often the 80% interval contained the truth, equitable threat score for rain, results by lead day and by month, and reliability tables for the rain probabilities.

Start with the lines `CRPSS vs emos`.

## Correction networks

`src/gnostiq/model.py` defines the two networks and their losses. There is nothing to run yet; training comes in the next branch.

Both are small: two hidden layers, 64 units by default. The physics is built into what the outputs mean, so no output ever needs clipping afterwards.

**Hourly network (temperature and dewpoint)**

- Temperature is the terrain-corrected forecast plus a learned correction.
- Dewpoint is temperature minus a depression, and the depression goes through a softplus, so it is always positive. Dewpoint cannot come out above temperature for any input or any weights.
- The last layer starts at zero. An untrained network returns the physics prior exactly, and training only has to learn what the prior gets wrong.
- Loss: CRPS of a normal distribution. Hours with no observed dewpoint still train the temperature side.

**Daily network (rain)**

- A probability of a wet day, and a gamma distribution for how much falls beyond the wet threshold.
- The mean amount is a learned efficiency times the moisture available in the column. Efficiency above `model.eff_max` (2 by default) is penalised. The cap is soft and above one because a day of converging air can rain out more than the column holds at any one moment.
- Loss: log loss for wet or dry, gamma log-likelihood for the amount on wet days.

`fit_stats` and `design` handle missing inputs. A predictor that is mostly empty or constant in training is left out; the odd missing value is filled with the training median.

`save` and `load` store a bundle: the weights for each seed, the scaling statistics and the settings. `predict_hourly` and `predict_daily` average over the seeds.

This branch adds PyTorch. The standard PyTorch download for Linux bundles about 2.5 GB of CUDA libraries for NVIDIA GPUs, which nothing here uses. Every tool is set up to fetch the CPU-only build from `https://download.pytorch.org/whl/cpu` instead:

| Tool | Where it is set | What happens |
|---|---|---|
| pip | `--extra-index-url` at the top of `requirements.txt` | pip sees `torch 2.15.0` on PyPI and `torch 2.15.0+cpu` on the PyTorch index, and takes `+cpu` because a local version sorts higher |
| uv | `[tool.uv.sources]` and `[[tool.uv.index]]` in `pyproject.toml` | torch comes from the PyTorch index on Linux and Windows, everything else from PyPI |
| Poetry | `[[tool.poetry.source]]` and `[tool.poetry.dependencies]` in `pyproject.toml` | torch comes from the PyTorch index, everything else from PyPI |
| Pipenv | a second `[[source]]` and `index = "pytorch-cpu"` on torch in `Pipfile` | Same |
| Hatch | `PIP_EXTRA_INDEX_URL` under `[tool.hatch.envs.default.env-vars]` | Hatch installs with pip, so it behaves as the pip row |
| PDM | `[[tool.pdm.source]]` with `include_packages = ["torch"]` and `exclude_packages = ["*"]` | torch comes only from the PyTorch index, everything else only from PyPI |

What was checked: each tool, asked to resolve this branch, went to the PyTorch index for torch, and Poetry, PDM and Pipenv went there for nothing else. The PyTorch index was unreachable from the machine these files were built on, so no tool was run through to an installed CPU build. If one of them still pulls `nvidia-*` packages, install torch on its own first, for example `pip install torch==2.15.0 --index-url https://download.pytorch.org/whl/cpu`, and run the install again.

PDM needs both settings. With `include_packages` alone it also looks up every other package on the PyTorch index.

Poetry, Pipenv and PDM send torch to the PyTorch index on macOS as well. uv uses PyPI on macOS, where the standard build has no CUDA in it anyway.

Use the requirements files with pip only. uv takes a package from the first index that has it, and the PyTorch index carries its own copies of numpy and other packages, so `uv pip install -r requirements.txt` can fail on a pin. With uv, use `uv sync`.

## Training

### Standard Python (`venv` / `virtualenv`)

```bash
gnostiq train  # or: gnostiq all
```

### uv

```bash
uv run gnostiq train  # or: gnostiq all
```

### Poetry

```bash
poetry run gnostiq train  # or: gnostiq all
```

### Pipenv

```bash
pipenv run gnostiq train  # or: gnostiq all
```

### Hatch

```bash
hatch run gnostiq train  # or: gnostiq all
```

### PDM

```bash
pdm run gnostiq train  # or: gnostiq all
```

fits both networks on the training window and writes:

- `data/models/hourly.pt` and `data/models/daily.pt`
- `data/processed/pred_hourly_model.parquet` and `pred_daily_model.parquet`, in the same layout as the baseline predictions, with `system = "gnostiq"`

After this, `gnostiq verify` puts the model on the scorecard next to the baselines. `gnostiq all` now runs build, baselines, train, verify.

How it trains:

- Every fifth calendar week of the training window is held out for early stopping. Whole weeks, because neighbouring hours are nearly copies of each other and a random split would leak.
- Adam, batches of 512. Training stops when the held-out loss has not improved for `model.patience` epochs, and the best weights are kept.
- `model.seeds` networks are trained from different starting points and averaged.
- The test window is never touched.

Each bundle records `cols`: the forecast inputs that actually had data during training. The live forecast uses that list to blank out anything the model never saw.

On a laptop CPU the default settings take a few minutes.

## Case replays

### Standard Python (`venv` / `virtualenv`)

```bash
gnostiq cases  # or: gnostiq all
```

### uv

```bash
uv run gnostiq cases  # or: gnostiq all
```

### Poetry

```bash
poetry run gnostiq cases  # or: gnostiq all
```

### Pipenv

```bash
pipenv run gnostiq cases  # or: gnostiq all
```

### Hatch

```bash
hatch run gnostiq cases  # or: gnostiq all
```

### PDM

```bash
pdm run gnostiq cases  # or: gnostiq all
```

picks the three wettest days of the test window and shows how the forecast for each one changed as the day approached, from seven days out to one. It writes `data/reports/cases.json` with, for the model, EMOS and the raw forecast at each lead: the chance of a wet day, the chance of a heavy day, and the median and 90th-percentile amount.

Only days the model forecast at every lead are eligible, so each replay is complete.

A scorecard tells you about the average day. These tell you what the system said before the days people remember. They are illustrations, not evidence: three days chosen for being extreme cannot show skill, and the selection favours whichever system happens to look good on them.

`gnostiq all` now runs build, baselines, train, verify, cases.

## Live forecast

### Standard Python (`venv` / `virtualenv`)

```bash
gnostiq run
```

### uv

```bash
uv run gnostiq run
```

### Poetry

```bash
poetry run gnostiq run
```

### Pipenv

```bash
pipenv run gnostiq run
```

### Hatch

```bash
hatch run gnostiq run
```

### PDM

```bash
pdm run gnostiq run
```

fetches the newest model run from Open-Meteo, applies the trained networks and writes `data/reports/forecast.json`. It needs the trained models in `data/models/` and the terrain file `data/processed/static.json`.

The document:

```
site, init_utc, base_model, model_trained, thresholds
hourly[]  valid_utc, lead_day, t2m{q10,q50,q90}, td2m{q10,q50,q90}, raw{t2m,td2m}
daily[]   date, start_utc, lead_day, p_wet, p_heavy, tp24{q50,q90}, raw_tp24
```

Two decisions worth knowing about:

- **Lead days are rounded up.** The archive's "day 2" forecast was issued somewhere between 48 hours and one model cycle more before the hour it describes. A live step 30 hours ahead is therefore treated as day 2, not day 1. The uncertainty shown errs on the wide side rather than the narrow one.
- **Inputs the model was not trained on are blanked.** The live API serves pressure levels, CAPE and column water vapour; the training archive does not. Letting them in would shift the terrain correction and the moisture estimate away from what was verified, so `run.py` removes any input missing from the bundle's `cols` list. A test checks that those fields cannot change the forecast.

The file is written to a temporary name and renamed, so the web server never reads half a file.

## API and web page

### Standard Python (`venv` / `virtualenv`)

```bash
gnostiq serve                             # http://127.0.0.1:8000
gnostiq serve --host 0.0.0.0 --port 8080
```

### uv

```bash
uv run gnostiq serve                             # http://127.0.0.1:8000
uv run gnostiq serve --host 0.0.0.0 --port 8080
```

### Poetry

```bash
poetry run gnostiq serve                             # http://127.0.0.1:8000
poetry run gnostiq serve --host 0.0.0.0 --port 8080
```

### Pipenv

```bash
pipenv run gnostiq serve                             # http://127.0.0.1:8000
pipenv run gnostiq serve --host 0.0.0.0 --port 8080
```

### Hatch

```bash
hatch run gnostiq serve                             # http://127.0.0.1:8000
hatch run gnostiq serve --host 0.0.0.0 --port 8080
```

### PDM

```bash
pdm run gnostiq serve                             # http://127.0.0.1:8000
pdm run gnostiq serve --host 0.0.0.0 --port 8080
```

| Path | Returns |
|---|---|
| `/` | The page |
| `/api/forecast` | `data/reports/forecast.json` |
| `/api/verify` | `data/reports/scorecard.json` |
| `/api/cases` | `data/reports/cases.json` |
| `/api/health` | `{"ok": true, "forecast_init_utc": ...}` |
| `/method` | `docs/METHOD.md` as plain text |

The API only reads files. A report that has not been generated yet returns 404 with a message naming it, and the page shows which command to run.

The page is one HTML file with no build step and no external scripts. It has three parts:

- **Forecast**: temperature and dewpoint with the 10th to 90th percentile band next to the raw model, and the daily chance of rain.
- **Verification**: skill by lead time with its intervals, the score table, and a reliability diagram for rain. The selector switches variable; `#t2m`, `#td2m` and `#tp24` in the address deep-link to one.
- **Heavy-rain cases**: one small chart per replayed day.

Every chart has a Table button with the same numbers, and the page follows the system light or dark setting. The footer carries the attribution Open-Meteo, NOAA, IEM and CHIRPS ask for; keep it if you restyle the page.

## End-to-end test

`tests/test_pipeline.py` drives the whole thing through the command line on synthetic data: `gnostiq all`, then `gnostiq run` with a stand-in for the live forecast, then the API. If a change breaks the wiring between two modules, this is the test that fails.

## Running it for real

After setting up with your tool as described under Setup:

### Standard Python (`venv` / `virtualenv`)

```bash
python scripts/gate.py  # then change the keys it lists in gnostiq.toml
gnostiq pull            # everything; safe to re-run
gnostiq all             # build, baselines, train, verify, cases
gnostiq run             # live forecast
gnostiq serve           # http://127.0.0.1:8000
```

### uv

```bash
uv run python scripts/gate.py  # then change the keys it lists in gnostiq.toml
uv run gnostiq pull            # everything; safe to re-run
uv run gnostiq all             # build, baselines, train, verify, cases
uv run gnostiq run             # live forecast
uv run gnostiq serve           # http://127.0.0.1:8000
```

### Poetry

```bash
poetry run python scripts/gate.py  # then change the keys it lists in gnostiq.toml
poetry run gnostiq pull            # everything; safe to re-run
poetry run gnostiq all             # build, baselines, train, verify, cases
poetry run gnostiq run             # live forecast
poetry run gnostiq serve           # http://127.0.0.1:8000
```

### Pipenv

```bash
pipenv run python scripts/gate.py  # then change the keys it lists in gnostiq.toml
pipenv run gnostiq pull            # everything; safe to re-run
pipenv run gnostiq all             # build, baselines, train, verify, cases
pipenv run gnostiq run             # live forecast
pipenv run gnostiq serve           # http://127.0.0.1:8000
```

### Hatch

```bash
hatch run python scripts/gate.py  # then change the keys it lists in gnostiq.toml
hatch run gnostiq pull            # everything; safe to re-run
hatch run gnostiq all             # build, baselines, train, verify, cases
hatch run gnostiq run             # live forecast
hatch run gnostiq serve           # http://127.0.0.1:8000
```

### PDM

```bash
pdm run python scripts/gate.py  # then change the keys it lists in gnostiq.toml
pdm run gnostiq pull            # everything; safe to re-run
pdm run gnostiq all             # build, baselines, train, verify, cases
pdm run gnostiq run             # live forecast
pdm run gnostiq serve           # http://127.0.0.1:8000
```

Read `data/reports/gate.md` first, then `data/reports/qc.md`, then `data/reports/scorecard.md`.

Method and limits are written up in [docs/METHOD.md](docs/METHOD.md).

## Deploy

Any small Linux server will do: one CPU and 1 GB of memory. Train on your own machine and ship the results. The server only produces the live forecast and serves the page.

On the server:

```
sudo useradd -r -m -d /opt/gnostiq gnostiq
sudo -u gnostiq git clone <your-remote> /opt/gnostiq/app
cd /opt/gnostiq/app && sudo -u gnostiq uv sync --no-dev
```

Or, without uv on the server:

```
cd /opt/gnostiq/app
sudo -u gnostiq python3.12 -m venv .venv
sudo -u gnostiq .venv/bin/pip install -r requirements.txt
sudo -u gnostiq .venv/bin/pip install -e . --no-deps
```

Either way the environment ends up in `/opt/gnostiq/app/.venv`, which is where the systemd units look for the `gnostiq` command.

The other tools work on a server too, as long as the environment lands in `.venv`:

| Tool | Install on the server | Environment in `.venv`? |
|---|---|---|
| Poetry | `poetry install --only main` | Only after `poetry config virtualenvs.in-project true` |
| Pipenv | `pipenv install` | Only with `PIPENV_VENV_IN_PROJECT=1` set |
| PDM | `pdm install --prod` | Yes, by default |
| Hatch | `hatch env create` | No. Point `ExecStart` in both units at the path `hatch env find` prints. |

From your machine, copy the trained models, the reports and the terrain file:

```
rsync -a --relative data/models data/reports data/processed/static.json <server>:/opt/gnostiq/app/
```

Then install the services from `deploy/`:

```
sudo cp deploy/gnostiq-api.service deploy/gnostiq-run.service deploy/gnostiq-run.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now gnostiq-api.service gnostiq-run.timer
sudo systemctl start gnostiq-run.service     # first forecast now, not in three hours
```

The timer refreshes the forecast every three hours. For HTTPS, install Caddy and put your domain in `deploy/Caddyfile`.

To check it: `curl localhost:8000/api/health` shows when the forecast was issued, and `journalctl -u gnostiq-run` shows the last run.

CI is in `.github/workflows/ci.yml`: lint and tests on every push and pull request. It installs without a lock file, so commit `uv.lock` and change the step to `uv sync --locked` once the stack is merged.

## Keeping it current

- The forecast refreshes itself through the timer.
- To extend training past the current test window: move the dates in `[window]`, run `gnostiq pull --refresh` then `gnostiq all` (with your tool's `run` prefix), and copy `data/models` and `data/reports` to the server again. Pick the new test window before you look at any scores for it.
- CHIRPS final data arrives around the third week of the following month. Until then recent days are preliminary, and `pull` replaces them when the final files appear.

## What has been checked, and what has not

The pipeline runs end to end and every test passes, on synthetic data. No real-data result exists. The download code has never been executed against the live servers; on 2026-11-17 the request formats were checked by hand in a browser.

| Source | Checked | Result |
|---|---|---|
| Open-Meteo archive, `ecmwf_ifs025`, core variables | Yes | Works. Grid cell centre 9.75 N 9.0 E, height 1182 m. |
| Same, CAPE and column water vapour | Yes | Served but all null |
| Same, pressure-level fields | Yes | Refused by the API |
| `gfs_seamless` | Yes | Works, including CAPE |
| `icon_seamless` | Yes | Works at short leads; day 7 is null |
| CHIRPS v3 file paths | Yes | Correct. Final `sat` files through October 2026. One request got a 429. |
| NOAA GHCNh station list and data file | No | They only download. The parser follows NOAA's documentation. |
| IEM METAR request | No | Parameters follow IEM's documentation |

## Assumptions to check on real data

1. **GHCNh file layout.** See "Not yet checked against a real file" under Station observations. This is the most likely thing to need a fix on the first run, and the gate exercises it first.
2. **CHIRPS day boundary.** Daily totals are treated as 00 to 00 UTC. If the product's day is offset, forecast and truth are misaligned by some hours.
3. **Station identity.** If the gate says the synoptic and METAR temperatures come from a "different site or sensor", `truth.temp = "merged"` mixes two instruments. Use `ghcnh` or `iem` alone.
4. **Station height.** The terrain correction is station height minus the model's 1182 m. At the listed 1295 m the model is cooled by about 0.7 degC. If the gate's barometer estimate disagrees with 1295 m, fix `site.elev_m` before training.
5. **Open-Meteo licence.** The free API is non-commercial. A commercial service needs their paid plan or your own ingest of ECMWF open data.

## Known gaps

- **No CAPE, column water vapour or pressure-level inputs.** The lead-time archive does not have them for ECMWF. The rain model's moisture supply is estimated from surface dewpoint, and the terrain correction uses the standard 6.5 K/km. Two ways to close this: use GFS CAPE as an extra predictor, since the archive has it, or pull whole ECMWF runs through Open-Meteo's Single Runs API, which is a bigger ingest job.
- **One site and one test season.** Nothing here shows the method carries over to other terrain.
- **The IFS changed cycle on 12 May 2026**, inside the default test window. Training data comes from the earlier cycle.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `pull` stops with a 400 on the core group | Open-Meteo rejected a variable or the model id. The message quotes the server's reason. Fix the id in `gnostiq.toml` or the name in `GROUPS` in `ingest/nwp.py`. |
| Warning `variable group 'levels' not served` | Expected. A `levels.missing` marker stops further attempts; `--refresh` tries again. |
| 429 or repeated retries | Rate limit. Wait, then re-run; finished downloads are skipped. |
| `removed N unreadable forecast chunk(s)` from `gnostiq all` | A download came back empty or cut off. Run `gnostiq pull --only nwp`, which fetches just those chunks, then `gnostiq all`. |
| `N GHCNh candidates ...` | Several station records match. Run the gate and set `site.ghcnh`. |
| CHIRPS log says many days not read | Usually the rate limit; re-run. If every read fails, open one URL from `precip.url()` in a browser. |
| `pairs have no train or no test rows` | The windows do not overlap the data. Check the last observation date in `data/reports/gate.md`. |
| `only N wet training days` | Rain truth is too sparse. Use `truth.rain = "chirps"`. |
| The page says "Not available yet" | The command it names has not been run, or `data/reports` was not copied to the server. |
