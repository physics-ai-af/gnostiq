# gnostiq

A correction layer for global weather model forecasts at a site. It takes the ECMWF forecast for the grid cell over the site, corrects it for the terrain and puts an uncertainty range on it. The result is checked against station observations from a wet season the model never saw, next to the standard baselines.

It runs for two sites in Nigeria. Both are in `gnostiq.toml`. Abuja has a station record good enough to train and score on. Jos does not, so it runs Abuja's networks on its own forecast and height; its only checks are NiMet's 2026 reports and the live check, and the page says so.

The tests use synthetic files written in the real on-disk formats. They show the code works, not that the forecasts are any good; the scorecard does that.

## Tests

Use the block for your tool.

### Standard Python (`venv` / `virtualenv`)

```
pytest                           # everything
python -m pytest                 # everything, explicit interpreter
pytest tests/test_seed_state.py  # one file
```

### uv

```
uv run pytest                           # everything
uv run pytest tests/test_seed_state.py  # one file
```

### Poetry

```
poetry run pytest                           # everything
poetry run pytest tests/test_seed_state.py  # one file
```

### Pipenv

```
pipenv run pytest                           # everything
pipenv run pytest tests/test_seed_state.py  # one file
```

### Hatch

```
hatch run pytest                           # everything
hatch run pytest tests/test_seed_state.py  # one file
```

### PDM

```
pdm run pytest                           # everything
pdm run pytest tests/test_seed_state.py  # one file
```

No test touches the network. Downloads are replaced with stand-ins, and anything that needs data uses synthetic files written in the real formats.

| Path | What it checks |
|---|---|
| `tests/conftest.py` | Shared fixtures: config writer, and from later branches the staged synthetic data |
| `tests/data/gnostiq.toml` | Frozen one-site config that the fixtures edit, so changing the real sites leaves the tests alone |
| `tests/test_cfg.py` | Config loading, lookup order, every validation rule, sites that borrow another's networks |
| `tests/test_io.py` | Caching, refresh by age, retries, missing files, fallback to a stale copy |
| `tests/test_requirements.py` | requirements files and Pipfile match pyproject.toml, with pins inside its ranges |
| `tests/synth.py` | Synthetic raw files in the real formats, used by the fixtures |
| `tests/test_station.py` | Parsing both sources, NOAA quality flags, trace rain, rain-day rules, station lookup, merge modes |
| `tests/data/GHCNh_NII0000DNJO_excerpt.psv` | Two rows of the real Jos airport record, with its full header |
| `tests/test_cli.py` | Argument handling, unknown sources, data directories, `--config`, helpful errors |
| `tests/test_gate.py` | Runs the script on a good record, a pinned id, a station away from the site, a daytime-only station and an empty lookup |
| `tests/test_nwp.py` | Parsing a real response, chunking, request contents, refused groups, assembly, live fallback |
| `tests/test_physics.py` | Formulas against known values, the terrain prior, wind sign, rain-day boundaries, fallbacks |
| `tests/test_precip.py` | File paths, pixel reads, nodata, incremental pulls, preliminary to final, refused days |
| `tests/test_static.py` | Terrain tile naming, model height from pressure, caching, the fallback order |
| `tests/test_qc.py` | Each check on cases it must catch and cases it must leave alone; the full run |
| `tests/test_align.py` | Split boundaries, the joins, rain-day sums, truth source selection, missing inputs |
| `tests/test_dist.py` | CRPS against sampling, point forecasts, rain quantiles and exceedance |
| `tests/test_baselines.py` | Each baseline recovers a known signal; no test-window leakage; persistence timing |
| `tests/test_verify.py` | Threat score, bootstrap, reliability bins, common cases, a baseline-only scorecard, rain against a second truth |
| `tests/test_tamsat.py` | Reads the unfilled estimate from the published layout, file names, which days are read, no files kept |
| `tests/test_model.py` | The untrained net returns the prior; constraints hold for random weights; losses; round trip |
| `tests/test_train.py` | Whole-week validation split, early stopping, spread correction, bundle contents, constraints, the scored model |
| `tests/test_curve.py` | Nested training sizes, identical test cases for every system, the written report |
| `tests/test_cases.py` | Case selection, ordering, completeness, and the saved file |
| `tests/test_run.py` | Lead-day rounding, coverage, physical consistency, input masking, other models, the archive, atomic write, a second site on borrowed networks |
| `tests/test_live.py` | One issue per day, common cases, scores against known reports, synops before METARs, no reports at all, the written report |
| `tests/test_nimet.py` | A real NiMet report, paging by month, units, off-hour and gross values, distance to the site |
| `tests/data/nimet_65134_excerpt.json` | One real Jos synop from NiMet's node, as served |
| `tests/test_season.py` | Every system on the same reports, no overlap with training, the default season, a borrowing site |
| `tests/test_publish.py` | First issue per day, the chain of records, repeat runs, tampering caught, dry run, verify without a config |
| `tests/test_api.py` | 404 before reports exist, reports served as written, every site beside the config, the page, the method note, the static export |
| `tests/test_pipeline.py` | The whole pipeline through the CLI, then the live run for both sites and the API |
| `tests/test_seed_state.py` | What goes on the state branch, what later runs keep out, sites outside data/, the workflow's commands |

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
| `requirements-dev.txt` | `-r requirements.txt` plus pytest and ruff (and httpx2, for the API tests, from `15-api-web` on) |

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

Everything that describes the run lives in one file, `gnostiq.toml` at the repo root. Code never hard-codes the site, the dates or the model. Settings shared by every site come first; then each site has a table of its own. The values below are the repo's.

Shared:

| Key | Value | Notes |
|---|---|---|
| `window.start` | 2021-01-01 | Start of the observation record |
| `window.train_end`, `test_start`, `test_end` | 2025-03-31, 2025-04-01, 2025-10-31 | The test window is the 2025 wet season. It must never overlap training. |
| `truth.temp` | `ghcnh` | `ghcnh`, `iem`, or `merged` (station first, METAR fills gaps) |
| `truth.rain` | `chirps` | `station` or `chirps` |
| `truth.chirps_flavor` | `sat` | `sat` or `rnl` |
| `nwp.base` | `ecmwf_ifs025` | The model being corrected |
| `nwp.extra` | GFS, ICON | Inputs to the networks and to `emos_multi`, and drawn raw on the page |
| `nwp.compare` | AIFS, ARPEGE, JMA, GEM | Optional. Scored raw and drawn on the page, never fed to the networks, so adding one needs no retrain |
| `nwp.start` | 2024-01-01 | Where the forecast archive begins |
| `forecast.lead_days` | 1 to 7 | |
| `forecast.wet_mm`, `heavy_mm` | 1, 10 | Rain thresholds |
| `model.*` | 3 seeds, 64 hidden units | Small on purpose |

Per site, in `[sites.<name>]`:

| Key | Abuja | Jos | Notes |
|---|---|---|---|
| table name | `abuja` | `jos` | Lowercase; it goes in URLs |
| `lat`, `lon`, `elev_m` | 9.0068, 7.2632, 342 | 9.6398, 8.8691, 1289.9 | From the gate |
| `wmo`, `icao` | 65125, DNAA | 65134, DNJO | The synoptic station and the airport |
| `ghcnh` | `NIM00065125` | `NII0000DNJO` | NOAA station id. Empty means look it up from the WMO number. |
| `bbox` | 8.8 to 9.2 N, 7.0 to 7.5 E | 9.4 to 10.1 N, 8.6 to 9.2 E | Search box for station records |
| `tz` | Africa/Lagos | Africa/Lagos | |
| `data` | `data/abuja` | `data/jos` | Relative to the config file, one per site. Git ignores `data/`. |
| `borrow` | | `abuja` | Optional: run that site's networks instead of training here |

The first site is the default for every command. `gnostiq --site jos <command>` (or `GNOSTIQ_SITE=jos`) picks another; `--all-sites` on `run`, `check` and `season` runs each in turn. The file is found by walking up from the working directory, through `GNOSTIQ_CFG`, or with `--config <file>`. `cfg.load()` validates it and reports every problem in one error, so you fix the file once rather than once per mistake.

### Sites without a record

A site with `borrow` set has no station record good enough to train on. It runs the networks trained for the named site on its own forecast and height. Because window, truth, model inputs, lead days and thresholds are shared, they always match what those networks were trained on. Commands that need a record of the site's own refuse to run for it; see the Jos notes under the live forecast. A site cannot borrow from one that borrows.

In code:

```python
from gnostiq import cfg

c = cfg.get()  # the default site, loaded once per process
c.site.lat, c.window.test_start, c.paths.raw
jos = cfg.load(site="jos")
[x.site.name for x in cfg.sites(c)]  # every site in the file
```

## Downloads

`gnostiq.io.fetch(url, path)` is the one place that talks to the network for plain files. It writes to `path` and never downloads the same file twice unless you give it a `max_age`. A 400 or 404 raises `io.Missing` straight away, since retrying will not make a missing file appear. Anything else is retried with a growing pause, and if a refresh fails but an older copy is on disk, the older copy is used with a warning.

## Station observations

Two sources of observed weather at the site:

- **NOAA GHCNh**: the full record of the synoptic station (the site's `wmo`, or the id in its `ghcnh`), one pipe-separated file.
- **Iowa Environmental Mesonet**: METAR reports from the airport (the site's `icao`), one CSV per year.

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

Run this before any modelling. It answers one question: is the site's record good enough to be the truth the forecasts are judged against?

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
| PASS | Good for temperature and for rain | `ghcnh`, `truth.temp`, `truth.rain = "station"` |
| PARTIAL | Temperature is good, the gauge record is not | `ghcnh` if the temperature comes from GHCNh, `truth.temp`, `truth.rain = "chirps"` |
| FAIL | No source meets the temperature thresholds | Read the hour-of-day table first |

The report ends with the keys to change, grouped under the site's table (`[sites.abuja]`) and `[truth]`. Every one already exists in `gnostiq.toml`, so edit the existing lines rather than pasting a second table of the same name, which TOML rejects. The gate checks the default site; `GNOSTIQ_SITE=jos python scripts/gate.py` checks another. `[truth]` is shared by every site.

If the station reports from more than 1 km away from the site's `lat`/`lon`, or more than 10 m from its `elev_m`, the report also gives the station's own coordinates. Use them: the forecast grid cell, the CHIRPS cell and the lapse-rate correction are all read at the configured site, so a site 25 km from the instrument verifies the wrong place.

What it measures:

- **Which station this is.** Every distinct latitude, longitude and elevation in the record, with dates. A change part-way through means the station moved. It also works the barometer's height out of the pressure readings, as a check on `elev_m`, and compares synoptic temperatures with METAR temperatures at the same hours to see whether they come from one instrument.
- **Temperature and dewpoint.** Monthly coverage of the eight synoptic hours, the share of days with a reading at each hour of the day, how many test-season days have both a pre-dawn and an afternoon reading, and the longest gap.
- **Rain.** How many wet-season days have a usable 24 h total, how many of those are explicit zeros, which hours the accumulation reports arrive at, and annual totals to hold against CHIRPS.

The thresholds are constants at the top of the script. They are working numbers, not a standard. Look at one real report before changing them.

A FAIL is often just a station that does not report at night. That shows up plainly in the hour-of-day table. Such a station can still verify daytime hours with `truth.temp = "merged"`, but then say so wherever you publish scores.

## Forecast archive

Past forecasts for the site's grid cell, from Open-Meteo's Previous Runs API. For every hour it gives the value that was forecast one day earlier, two days earlier, and so on up to seven. That is what makes it possible to train and score by lead time without storing every model run.

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
- The extra models feed the networks their core group only, so only that is fetched. Models in `nwp.compare` are only scored, so they get a `point` group: temperature, dewpoint and rain.

### What the live archive actually serves

Checked by hand in a browser on 2026-11-17:

| Request | Result |
|---|---|
| `ecmwf_ifs025`, core variables | Works. Lead days 1 and 7 both filled. Grid cell centre 9.75 N 9.0 E, height 1182 m. |
| `ecmwf_ifs025`, CAPE and column water vapour | Served, but every value is null |
| `ecmwf_ifs025`, pressure-level fields | Refused with a 400. Expect one warning on the first pull. |
| `gfs_seamless` | Works, including CAPE |
| `icon_seamless` | Works at short leads. Lead day 7 is null. |
| `ecmwf_aifs025_single` | Works from some point in 2024 (null on 2024-03-01, filled by 2025-04-01). 6-hourly steps, so hourly values are interpolated. Checked 2026-11-19. |
| `meteofrance_arpege_world` | Works to lead day 4; days 5 to 7 are null. Checked 2026-11-19. |
| `jma_gsm`, `gem_global` | Work, lead days 1 to 7. Checked 2026-11-19. |
| `ukmo_global_deterministic_10km` | Null for April 2025, so left out |

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
- The server rate-limits, and answers 429 to readers that go too fast. The pull reads one day at a time with a one-second pause, and the days the model trains and tests on (from `nwp.start`) come first, so a stopped run still leaves those on file. A day it refuses is not stored, so the next pull tries it again. Re-run until the log says `0 not read`. It reads only up to the end of the test season, since later days are never scored, and saves every 50 days. The 2021 to 2025 window is about 1,800 reads. Each one is a few round trips to California, so on a slow connection plan on a few hours; a server in Europe or the US gets through it much faster.

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

## Training tables

`align.py` joins forecasts to observations. It is the last step of `gnostiq build`.

| File | One row per | Holds |
|---|---|---|
| `data/processed/pairs_hourly.parquet` | valid hour and lead day | the forecast columns, the physics features, observed `o_t2m` and `o_td2m`, and `split` |
| `data/processed/pairs_daily.parquet` | rain day and lead day | daily forecast aggregates, the moisture supply `pw`, observed `o_tp24`, and `split` |

`split` is `train` from `nwp.start` to `window.train_end`, `test` inside the test window, and `other` for everything else. Nothing labelled `test` is used for fitting anywhere in the code. `other` covers days after the test window ends: kept, never fitted on, never scored.

Each extra model in `nwp.extra` is joined onto the base forecast by valid hour and lead day, as three columns: `x_<model>_dt2m` and `x_<model>_dtd2m`, its temperature and dewpoint minus the base model's, and `x_<model>_ok`, 1 where it had a forecast. Offsets rather than raw values, so the network learns when to trust which model; ICON has no day 7, and `ok` tells the network so.

Rain days start at 06 UTC when the truth is the station gauge, because that is how synoptic rain is reported, and at 00 UTC when the truth is CHIRPS. The forecast is summed over whichever day the truth uses.

A pair where the observation and the terrain-corrected forecast differ by more than 15 degC is dropped. At that size one of the two is broken, and there is no way to tell which from here.

If either table ends up with no training rows or no test rows, the build stops and says so. That nearly always means the windows in the config do not overlap the data that was pulled.

## Baselines

These are the forecasts the model has to beat. They are built before the model exists, so the bar is fixed first.

### Standard Python (`venv` / `virtualenv`)

```
gnostiq baselines
```

### uv

```
uv run gnostiq baselines
```

### Poetry

```
poetry run gnostiq baselines
```

### Pipenv

```
pipenv run gnostiq baselines
```

### Hatch

```
hatch run gnostiq baselines
```

### PDM

```
pdm run gnostiq baselines
```

| System | Temperature and dewpoint | Rain |
|---|---|---|
| `clim` | Harmonic fit to the station record: annual cycle, daily cycle and their interaction | What fell within 15 days of that calendar date in earlier years |
| `persist` | The observation one lead time earlier | The last complete day's total at the time the forecast was issued |
| `raw` | The model's grid-cell value | The model's 24 h total |
| `lapse` | `raw` moved to station height | not applicable |
| `emos` | Gaussian regression on the terrain-corrected forecast, fitted by minimum CRPS, one fit per lead day | Logistic regression for wet or dry, gamma regression for the amount |
| `emos_multi` | `emos` with each extra model's offset as another predictor | not applicable |
| `raw:<model>` | Each extra model, raw | Same |

`emos` is the one that counts. `emos_multi` is there because the network also sees the extra models: it gets the same inputs through the standard method, so a win over it is a win for the method, not for having more models. Beating a raw model that sits 113 m too low proves very little. A method that cannot beat a standard statistical correction has not earned its complexity.

Climatology is fitted only on observations before the test window. Persistence only uses observations that existed when the forecast was issued. Both are tested.

Outputs, both under `data/processed/`:

- `pred_hourly_base.parquet`: `valid`, `lead_day`, `split`, `var`, `obs`, `system`, `mu`, `sigma`. `sigma` is empty for systems that give a single value.
- `pred_daily_base.parquet`: `day`, `lead_day`, `split`, `obs`, `system`, `p1` and `p10` (chance of at least the wet and heavy thresholds), and 99 quantiles `q01` to `q99`.

`dist.py` has the scoring maths these share with the scorecard: CRPS for a normal distribution, CRPS from quantiles, and the rain distribution, which is a point mass at zero plus a gamma above the wet threshold.

## Scorecard

### Standard Python (`venv` / `virtualenv`)

```
gnostiq verify  # or: gnostiq all
```

### uv

```
uv run gnostiq verify  # or: gnostiq all
```

### Poetry

```
poetry run gnostiq verify  # or: gnostiq all
```

### Pipenv

```
pipenv run gnostiq verify  # or: gnostiq all
```

### Hatch

```
hatch run gnostiq verify  # or: gnostiq all
```

### PDM

```
pdm run gnostiq verify  # or: gnostiq all
```

scores every system on the test window and writes `data/reports/scorecard.md` for reading and `scorecard.json` for the web page.

It runs as soon as the baselines exist. Until the model has been trained the card simply has no `gnostiq` row and no skill section. That is deliberate: you can look at how good the baselines are before you have anything to compare them with.

How it keeps the comparison fair:

- **Same cases for everyone.** A case counts only if every core system produced a forecast for it. The extra models can lack cases (ICON has no day 7); their smaller `n` is shown and they are not directly comparable.
- **Proper scores.** CRPS for all three variables, Brier score at the wet and heavy thresholds. For a system that gives a single number, CRPS is the absolute error, so point forecasts and probabilistic ones sit in one column.
- **Honest intervals.** Skill is `1 - score / reference score`. Its 95% interval comes from resampling whole days 1,000 times, because errors within one day are not independent. An interval that includes zero is not evidence of skill, and the report says so at the top.

Also reported: bias, mean absolute error, how often the 80% interval contained the truth, equitable threat score for rain, results by lead day and by month, and reliability tables for the rain probabilities.

Start with the lines `CRPSS vs emos`, then `CRPSS vs emos_multi`: the same standard method given the same extra models the network sees. A lead over both is a lead for the method itself.

### Rain against a second truth

Every rain system is fitted to CHIRPS, so a rain score is partly a score of agreement with CHIRPS. If TAMSAT has been pulled, the scorecard scores the same rain forecasts against it as well, in a section of its own:

#### Standard Python (`venv` / `virtualenv`)

```
gnostiq pull --only tamsat  # the test window only, about 1 MB a day
gnostiq verify
```

#### uv

```
uv run gnostiq pull --only tamsat  # the test window only, about 1 MB a day
uv run gnostiq verify
```

#### Poetry

```
poetry run gnostiq pull --only tamsat  # the test window only, about 1 MB a day
poetry run gnostiq verify
```

#### Pipenv

```
pipenv run gnostiq pull --only tamsat  # the test window only, about 1 MB a day
pipenv run gnostiq verify
```

#### Hatch

```
hatch run gnostiq pull --only tamsat  # the test window only, about 1 MB a day
hatch run gnostiq verify
```

#### PDM

```
pdm run gnostiq pull --only tamsat  # the test window only, about 1 MB a day
pdm run gnostiq verify
```

TAMSAT v3.1 is a daily satellite estimate for all of Africa at 0.0375 degrees, from the University of Reading, open under a Creative Commons licence. Each day's file is read for the same 3 by 3 cells around the site as CHIRPS, then deleted; only the values are kept, in `data/raw/tamsat/tamsat.parquet`. The unfilled `rfe` field is used, not `rfe_filled`, which patches gaps with climatology. It is only used when CHIRPS is the rain truth, as both are treated as 00 to 00 UTC days.

Skill that holds against both truths is skill. Skill against one only is agreement with that product.

Not yet checked against a real file: the reader follows the published layout (two variables, `rfe` and `rfe_filled`, latitude ascending) and is tested on a file built that way. If `pull` logs that a day could not be read, open one file with `gdalinfo` and compare.

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

```
gnostiq train  # or: gnostiq all
```

### uv

```
uv run gnostiq train  # or: gnostiq all
```

### Poetry

```
poetry run gnostiq train  # or: gnostiq all
```

### Pipenv

```
pipenv run gnostiq train  # or: gnostiq all
```

### Hatch

```
hatch run gnostiq train  # or: gnostiq all
```

### PDM

```
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
- The extra models enter as inputs (see the training tables section).
- The spread is then corrected on the held-out weeks: one factor each for temperature and dewpoint, chosen to minimise CRPS there, and stored in the bundle as `inflate`. The networks learn their spread on rows they have already fitted, so without it the forecast ranges come out too narrow.
- The test window is never touched.

Each bundle records `cols`: the forecast inputs that actually had data during training. The live forecast uses that list to blank out anything the model never saw.

On a laptop CPU the default settings take a few minutes.

### Learning curve

#### Standard Python (`venv` / `virtualenv`)

```
gnostiq curve
```

#### uv

```
uv run gnostiq curve
```

#### Poetry

```
poetry run gnostiq curve
```

#### Pipenv

```
pipenv run gnostiq curve
```

#### Hatch

```
hatch run gnostiq curve
```

#### PDM

```
pdm run gnostiq curve
```

answers "how much archive does this need?". It refits EMOS, `emos_multi` and the network on 1, 2, 3 and 6 months of training pairs and on all of them, and scores every size on the same test cases. The months are whole weeks drawn at random from the training window, so each size spans the seasons, and each size contains the smaller ones. Climatology always uses the full station record, since it needs no archived forecasts.

It writes `data/reports/curve.md` and `curve.json`. Read `vs emos` down the table: if the network stays ahead of EMOS as the archive shrinks, the method is earning its keep on little data. It takes a few minutes and is not part of `gnostiq all`.

## Case replays

### Standard Python (`venv` / `virtualenv`)

```
gnostiq cases  # or: gnostiq all
```

### uv

```
uv run gnostiq cases  # or: gnostiq all
```

### Poetry

```
poetry run gnostiq cases  # or: gnostiq all
```

### Pipenv

```
pipenv run gnostiq cases  # or: gnostiq all
```

### Hatch

```
hatch run gnostiq cases  # or: gnostiq all
```

### PDM

```
pdm run gnostiq cases  # or: gnostiq all
```

picks the three wettest days of the test window and shows how the forecast for each one changed as the day approached, from seven days out to one. It writes `data/reports/cases.json` with, for the model, EMOS and the raw forecast at each lead: the chance of a wet day, the chance of a heavy day, and the median and 90th-percentile amount.

Only days the model forecast at every lead are eligible, so each replay is complete.

A scorecard tells you about the average day. These tell you what the system said before the days people remember. They are illustrations, not evidence: three days chosen for being extreme cannot show skill, and the selection favours whichever system happens to look good on them.

`gnostiq all` now runs build, baselines, train, verify, cases.

## Live forecast

### Standard Python (`venv` / `virtualenv`)

```
gnostiq run
```

### uv

```
uv run gnostiq run
```

### Poetry

```
poetry run gnostiq run
```

### Pipenv

```
pipenv run gnostiq run
```

### Hatch

```
hatch run gnostiq run
```

### PDM

```
pdm run gnostiq run
```

fetches the newest model run from Open-Meteo, applies the trained networks and writes `forecast.json` to the site's `reports/` directory (`data/abuja/reports/` for Abuja). It needs the trained models in `models/`, and fetches the terrain file `processed/static.json` first if it is missing.

The document:

```
site, init_utc, base_model, model_trained, trained_at, thresholds
hourly[]  valid_utc, lead_day, t2m{q10,q50,q90}, td2m{q10,q50,q90}, raw{t2m,td2m}, lapse{t2m,td2m},
          models{<extra model>{t2m,td2m}}, clim{t2m{q10,q50,q90}, td2m{q10,q50,q90}}
daily[]   date, start_utc, lead_day, p_wet, p_heavy, tp24{q50,q90}, raw_tp24
```

Two decisions worth knowing about:

- **Lead days are rounded up.** The archive's "day 2" forecast was issued somewhere between 48 hours and one model cycle more before the hour it describes. A live step 30 hours ahead is therefore treated as day 2, not day 1. The uncertainty shown errs on the wide side rather than the narrow one.
- **Inputs the model was not trained on are blanked.** The live API serves pressure levels, CAPE and column water vapour; the training archive does not. Letting them in would shift the terrain correction and the moisture estimate away from what was verified, so `run.py` removes any input missing from the bundle's `cols` list. A test checks that those fields cannot change the forecast.

`lapse` is the base model moved to the site's height and nothing else, the physics on its own. `trained_at` names the site the networks were trained for. `models` holds each extra model's raw forecast, fetched live, so the page can draw them next to Gnostiq; a model that is down shows as missing and the forecast still runs. `clim` is the usual range for that hour and date from the station record, and needs `interim/obs.parquet`; a site without a record has none.

The file is written to a temporary name and renamed, so the web server never reads half a file. Each run also saves what it issued to `archive/<init>.parquet`: one row per system, variable and hour, exactly as the page showed it (`mu`, `sigma`, and the band as drawn in `q10` and `q90`). Nothing is ever deleted from it, so `check --days` can look back as far as the archive goes.

### Live check

#### Standard Python (`venv` / `virtualenv`)

```
gnostiq check
```

#### uv

```
uv run gnostiq check
```

#### Poetry

```
poetry run gnostiq check
```

#### Pipenv

```
pipenv run gnostiq check
```

#### Hatch

```
hatch run gnostiq check
```

#### PDM

```
pdm run gnostiq check
```

scores those saved forecasts against the station reports that came in afterwards, over the last 30 days (`--days` changes that). It keeps the first forecast issued on each UTC day so a day of 3-hourly runs counts once, and scores Gnostiq, each raw model, the height-corrected base model and the normal range on the same reports. It writes `live.json` and `live.md` beside the forecast; the page shows them under "Last 30 days".

The same report also puts forecast and outcome side by side for the last 7 days, under `recent` in `live.json`: for every hour, the day-ahead forecast as shown (Gnostiq's median and 80% band, raw and height-corrected ECMWF) next to the report, how often the report fell inside the band, and each day's high and low as reported and as forecast. A high is taken over the reported hours from 11:00 to 17:00 local time and a low over those from 04:00 to 08:00, each needing at least two, so forecast and report cover the same hours and a daytime-only station still gets its highs. On the page this is a chart per variable with the reports as dots over the band, and a table of every report.

### Track record

Every check also adds to `track` in `live.json`: one row per day since the first saved forecast, with the high, the low and the day's average error, as forecast up to a day before by Gnostiq and raw ECMWF and as reported, the share of reported hours inside Gnostiq's 80% range, and the Auto Drive record of the forecast behind the day once publishing is on. Days older than the 30-day window are carried over from the previous `live.json`, so the record keeps growing; a day seen again keeps whichever version saw more reported hours. `summary` gives, for highs and lows, the average error and how often each system was within 1 C.

`season.json` carries the same `track` for the rebuilt season, so there is something to read before the live record is long. The page's "Track record" section shows either, with a switch: the live record once it has two weeks, the rebuilt season until then. The two are labelled apart, since one was issued at the time and the other was rebuilt afterwards.

Reports come from two places, and the first wins where both have the hour:

- **NiMet synops** (`ingest/nimet.py`), from the WIS2 node NiMet started in January 2026, decoded to GeoJSON by the node's own API. Tenths of a degree, and at Abuja night-time hours too.
- **Airport METARs** from IEM. Whole degrees, which adds about 0.3 C of noise to every system alike.

If one source is down the other is used; the log says which failed. `reports` and `sources` in `live.json` count what came in, so an empty feed reads as empty rather than as no skill.

This is the evidence that cannot be tuned after the fact: every forecast was saved before the weather happened. Skill intervals need five days of reports before they appear, and a few weeks before they are tight.

On a server, `deploy/gnostiq-check.timer` runs it every morning.

### NiMet reports

#### Standard Python (`venv` / `virtualenv`)

```
gnostiq pull --only nimet  # not part of a plain pull
```

#### uv

```
uv run gnostiq pull --only nimet  # not part of a plain pull
```

#### Poetry

```
poetry run gnostiq pull --only nimet  # not part of a plain pull
```

#### Pipenv

```
pipenv run gnostiq pull --only nimet  # not part of a plain pull
```

#### Hatch

```
hatch run gnostiq pull --only nimet  # not part of a plain pull
```

#### PDM

```
pdm run gnostiq pull --only nimet  # not part of a plain pull
```

asks NiMet's node for every report from the site's `wmo` station, a month at a time and 500 values a page, and keeps the pages under `raw/nimet/`. Past months are never fetched again; the current month is refreshed hourly. Each report arrives as one record per measured value; temperature, dewpoint, station and sea-level pressure and wind speed are kept, reports more than ten minutes off the hour are dropped, and the same gross limits as the other sources apply.

Checked against the live node on 2026-11-19, from a cloud browser:

| Station | Records | Notes |
|---|---|---|
| ABUJA, `0-20000-0-65125` | about 43,500 values for April to October 2026, including 00 UTC | Listed at 9.020 N 7.275 E, 354 m |
| JOS, `0-20000-0-65134` | about 10,500 values for April to October 2026, daytime only (08 to 17 UTC) | Listed at 9.867 N 8.900 E, 1290 m: the old position, 25 km north of the airport. Which instrument this is needs settling before it is treated as the airport. |
| University of Jos, IITA Abuja | Registered, nothing published | |

Rain amounts are in some reports, but without the period they cover, so they are not used.

The node timed out from at least one Nigerian home connection while answering from elsewhere. If it does for you, run the commands that need it (`check`, `season`) from the server or pod, or another network. A failed NiMet fetch gives up after about two minutes.

### Season check

#### Standard Python (`venv` / `virtualenv`)

```
gnostiq season                                      # the latest wet season with a month in it
gnostiq season --start 2026-04-01 --end 2026-10-31
gnostiq season --all-sites
```

#### uv

```
uv run gnostiq season                                      # the latest wet season with a month in it
uv run gnostiq season --start 2026-04-01 --end 2026-10-31
uv run gnostiq season --all-sites
```

#### Poetry

```
poetry run gnostiq season                                      # the latest wet season with a month in it
poetry run gnostiq season --start 2026-04-01 --end 2026-10-31
poetry run gnostiq season --all-sites
```

#### Pipenv

```
pipenv run gnostiq season                                      # the latest wet season with a month in it
pipenv run gnostiq season --start 2026-04-01 --end 2026-10-31
pipenv run gnostiq season --all-sites
```

#### Hatch

```
hatch run gnostiq season                                      # the latest wet season with a month in it
hatch run gnostiq season --start 2026-04-01 --end 2026-10-31
hatch run gnostiq season --all-sites
```

#### PDM

```
pdm run gnostiq season                                      # the latest wet season with a month in it
pdm run gnostiq season --start 2026-04-01 --end 2026-10-31
pdm run gnostiq season --all-sites
```

rebuilds what each system would have issued over a whole past season from the forecast archive, lead day by lead day, and scores it against NiMet reports: Gnostiq, EMOS and multi-model EMOS fitted on the training window, the raw models, the height-corrected base model, and the normal range where the site has a station record. It refuses a season that overlaps training. It writes `season.json` and `season.md`; the page shows them under "Season check".

To bring the rebuilt record up to the start of the live one, end it yesterday:

#### Standard Python (`venv` / `virtualenv`)

```
gnostiq --site jos pull --only nwp,nimet
gnostiq pull --only nwp,nimet
gnostiq season --all-sites --start 2026-04-01
```

#### uv

```
uv run gnostiq --site jos pull --only nwp,nimet
uv run gnostiq pull --only nwp,nimet
uv run gnostiq season --all-sites --start 2026-04-01
```

#### Poetry

```
poetry run gnostiq --site jos pull --only nwp,nimet
poetry run gnostiq pull --only nwp,nimet
poetry run gnostiq season --all-sites --start 2026-04-01
```

#### Pipenv

```
pipenv run gnostiq --site jos pull --only nwp,nimet
pipenv run gnostiq pull --only nwp,nimet
pipenv run gnostiq season --all-sites --start 2026-04-01
```

#### Hatch

```
hatch run gnostiq --site jos pull --only nwp,nimet
hatch run gnostiq pull --only nwp,nimet
hatch run gnostiq season --all-sites --start 2026-04-01
```

#### PDM

```
pdm run gnostiq --site jos pull --only nwp,nimet
pdm run gnostiq pull --only nwp,nimet
pdm run gnostiq season --all-sites --start 2026-04-01
```

For Abuja, trained to March 2025 and tested on the 2025 wet season, the 2026 season is a second test it never saw. For Jos it is the first test of any kind: the networks and EMOS fitted at Abuja, run on Jos's own forecasts. Run `gnostiq --site jos pull --only nwp,nimet` first.

Read it with three things in mind:

- At Jos only daytime hours are scored; `hours` in `season.json` lists them.
- The report states how far the NiMet station is from the forecast point. For Jos that is 25 km on the listed position.
- ECMWF changed the IFS cycle on 12 May 2026, partway through the 2026 season, and the networks were trained on the old one. `by_month` shows whether skill shifts across that date.

### Public record on Auto Drive

#### Standard Python (`venv` / `virtualenv`)

```
gnostiq publish --all-sites            # a dry run until AUTO_DRIVE_API_KEY is set
gnostiq verify-record <cid>            # anyone; needs no config, data or key
gnostiq verify-record <cid> --depth 7
```

#### uv

```
uv run gnostiq publish --all-sites            # a dry run until AUTO_DRIVE_API_KEY is set
uv run gnostiq verify-record <cid>            # anyone; needs no config, data or key
uv run gnostiq verify-record <cid> --depth 7
```

#### Poetry

```
poetry run gnostiq publish --all-sites            # a dry run until AUTO_DRIVE_API_KEY is set
poetry run gnostiq verify-record <cid>            # anyone; needs no config, data or key
poetry run gnostiq verify-record <cid> --depth 7
```

#### Pipenv

```
pipenv run gnostiq publish --all-sites            # a dry run until AUTO_DRIVE_API_KEY is set
pipenv run gnostiq verify-record <cid>            # anyone; needs no config, data or key
pipenv run gnostiq verify-record <cid> --depth 7
```

#### Hatch

```
hatch run gnostiq publish --all-sites            # a dry run until AUTO_DRIVE_API_KEY is set
hatch run gnostiq verify-record <cid>            # anyone; needs no config, data or key
hatch run gnostiq verify-record <cid> --depth 7
```

#### PDM

```
pdm run gnostiq publish --all-sites            # a dry run until AUTO_DRIVE_API_KEY is set
pdm run gnostiq verify-record <cid>            # anyone; needs no config, data or key
pdm run gnostiq verify-record <cid> --depth 7
```

`publish` stores the first forecast of each UTC day, the one the live check scores, on Autonomys Auto Drive, with a record beside it: the forecast's CID and SHA-256, when it was issued and uploaded, the site, hashes of the trained networks and of `gnostiq.toml`, the package version and commit, the input models, the training window and truth sources, and the CID of the site's previous record. Each record names the one before it, so the latest CID reaches every earlier one, and none can be changed without the next one still naming the original.

`run` keeps the forecast's own bytes as `archive/<init>.json.gz`, gzipped with a fixed timestamp so the same forecast is always the same CID; that file is what gets uploaded. Days missed up to three days back are caught up (`--days` changes that). The site's `reports/records.json` lists every record, the latest CID and the bytes stored, copies go to `published/`, and the page shows the latest record under the forecast.

Without the key nothing leaves the machine: `publish` writes the record it would have stored to `published/<day>.dry-run.json`. Uploads are permanent and count against the account's monthly upload allowance, 20 MB on the free tier, so try the dry run first. One forecast and record come to about 14 KB, under 1 MB a month for both sites. Get a key at ai3.storage under Developers, then:

```
export AUTO_DRIVE_API_KEY=...  # Git Bash; on the server see Deploy
gnostiq publish --all-sites
```

Publish from one place only. Two machines publishing the same site each start their own chain, and the same day is stored twice.

`verify-record` fetches each record and its forecast from the public gateway, checks the forecast against its hash and that it is the issue and site the record says, and follows `previous`. It exits 1 if any record fails. [docs/PROVENANCE.md](docs/PROVENANCE.md) has the record format, how to check one with `curl` and `sha256sum` alone, and storage needs.

### A second site: Jos

Jos failed the gate: its synoptic record stops in 2021 and the airport reports only by day. Nothing can be trained or scored there, so its table in `gnostiq.toml` has `borrow = "abuja"` (see Sites without a record under Configuration). Its forecast is Abuja's networks run on Jos's own ECMWF forecast, after the terrain correction for Jos's height. The model grid sits well below the plateau (1182 m for the cell the old Jos point fell in, against 1290 m at the airport), where at Abuja the gap is 23 m, so the height step does more work here. `pull` measures the height of the cell actually used.

#### Standard Python (`venv` / `virtualenv`)

```
gnostiq --site jos pull    # only the terrain height; nothing else is needed
gnostiq --site jos run
gnostiq --site jos check
gnostiq --site jos season  # after pull --only nwp,nimet
gnostiq run --all-sites    # every site in gnostiq.toml, one after another
gnostiq check --all-sites
```

#### uv

```
uv run gnostiq --site jos pull    # only the terrain height; nothing else is needed
uv run gnostiq --site jos run
uv run gnostiq --site jos check
uv run gnostiq --site jos season  # after pull --only nwp,nimet
uv run gnostiq run --all-sites    # every site in gnostiq.toml, one after another
uv run gnostiq check --all-sites
```

#### Poetry

```
poetry run gnostiq --site jos pull    # only the terrain height; nothing else is needed
poetry run gnostiq --site jos run
poetry run gnostiq --site jos check
poetry run gnostiq --site jos season  # after pull --only nwp,nimet
poetry run gnostiq run --all-sites    # every site in gnostiq.toml, one after another
poetry run gnostiq check --all-sites
```

#### Pipenv

```
pipenv run gnostiq --site jos pull    # only the terrain height; nothing else is needed
pipenv run gnostiq --site jos run
pipenv run gnostiq --site jos check
pipenv run gnostiq --site jos season  # after pull --only nwp,nimet
pipenv run gnostiq run --all-sites    # every site in gnostiq.toml, one after another
pipenv run gnostiq check --all-sites
```

#### Hatch

```
hatch run gnostiq --site jos pull    # only the terrain height; nothing else is needed
hatch run gnostiq --site jos run
hatch run gnostiq --site jos check
hatch run gnostiq --site jos season  # after pull --only nwp,nimet
hatch run gnostiq run --all-sites    # every site in gnostiq.toml, one after another
hatch run gnostiq check --all-sites
```

#### PDM

```
pdm run gnostiq --site jos pull    # only the terrain height; nothing else is needed
pdm run gnostiq --site jos run
pdm run gnostiq --site jos check
pdm run gnostiq --site jos season  # after pull --only nwp,nimet
pdm run gnostiq run --all-sites    # every site in gnostiq.toml, one after another
pdm run gnostiq check --all-sites
```

Commands that need a record of the site's own (`build`, `baselines`, `train`, `curve`, `verify`, `cases`, `all`) refuse to run for Jos; `season` runs, since it needs no record of Jos's own. With `--all-sites`, a site that fails is logged and the rest still run.

What this does and does not show. It is not verified at Jos. The networks learned Abuja's corrections from Abuja's weather, and Jos inputs sit at the cool edge of what they saw, so the correction may not carry over; the uncertainty band is Abuja's and is probably too narrow on the plateau. The page says so above the Jos forecast. Two checks exist: the season check above, against NiMet's 2026 Jos reports, and the live check, as reports come in. Both score Gnostiq against the height-corrected ECMWF line, which is the question that matters: does what was learned at Abuja add anything at Jos beyond the physics.

## API and web page

### Standard Python (`venv` / `virtualenv`)

```
gnostiq serve                             # http://127.0.0.1:8000
gnostiq serve --host 0.0.0.0 --port 8080
```

### uv

```
uv run gnostiq serve                             # http://127.0.0.1:8000
uv run gnostiq serve --host 0.0.0.0 --port 8080
```

### Poetry

```
poetry run gnostiq serve                             # http://127.0.0.1:8000
poetry run gnostiq serve --host 0.0.0.0 --port 8080
```

### Pipenv

```
pipenv run gnostiq serve                             # http://127.0.0.1:8000
pipenv run gnostiq serve --host 0.0.0.0 --port 8080
```

### Hatch

```
hatch run gnostiq serve                             # http://127.0.0.1:8000
hatch run gnostiq serve --host 0.0.0.0 --port 8080
```

### PDM

```
pdm run gnostiq serve                             # http://127.0.0.1:8000
pdm run gnostiq serve --host 0.0.0.0 --port 8080
```

| Path | Returns |
|---|---|
| `/` | The page; `/?site=jos` opens another site, `/?page=compare` the comparison page |
| `/api/sites` | Every site beside the config: name, the site its networks were trained at, its config file, position, compared models |
| `/api/<site>/forecast` | That site's `forecast.json` |
| `/api/<site>/verify` | `scorecard.json` |
| `/api/<site>/cases` | `cases.json` |
| `/api/<site>/live` | `live.json` |
| `/api/<site>/season` | `season.json` |
| `/api/forecast`, `/api/verify`, `/api/cases`, `/api/live` | The same for the first site, as before |
| `/api/health` | `{"ok": true, "forecast_init_utc": ..., "sites": {<site>: ...}}` |
| `/method` | `docs/METHOD.md` as plain text |

`gnostiq serve` serves every site in `gnostiq.toml`, the one it was started with first, so both Abuja and Jos are on the page.

The API only reads files. A report that has not been generated yet returns 404 with a message naming it, and the page shows which command to run.

The page is one HTML file with no build step and no external scripts. With more than one site there is a switcher at the top, and beside it a switch between the forecast page and the comparison page. The forecast page has six parts:

- **Forecast**: temperature and dewpoint with the 10th to 90th percentile band next to the raw models, and the daily chance of rain. The models in `nwp.compare` sit behind a "Show more models" button, so the default chart stays readable. For a site on borrowed networks a note says where they were trained and that the site is unverified, and the height-corrected base model is drawn too.
- **Last 30 days**: the live check. First what the page forecast a day ahead against what was reported, hour by hour over the last week, with daily highs and lows; then error by day and the score tables.
- **Track record**: day by day, the day-ahead high, low and average error against what was reported, for the live record or the rebuilt season.
- **Season check**: a whole past season against NiMet reports, CRPS by lead day and the score table.
- **Verification**: skill by lead time with its intervals, the score table, a reliability diagram for rain, and the rain scores against TAMSAT when it has been pulled. The selector switches variable; `#t2m`, `#td2m` and `#tp24` in the address deep-link to one.
- **Heavy-rain cases**: one small chart per replayed day.

A site on borrowed networks has no scorecard or case replays; those two parts link to the site the networks came from.

The comparison page, `?page=compare`, answers one question per variable: is Gnostiq better, and than what? It opens with a verdict against the best alternative, the system with the lowest error among those Gnostiq has a skill range against: better if the whole range is above zero, worse if below, tied otherwise. Below that are Gnostiq's skill against every alternative with its 95% range, every system's error from best to worst, and the error month by month for Gnostiq, the best alternative, raw ECMWF and ECMWF's AI model. It switches between the rebuilt season and the live record. Both checks now give a skill range against each raw model too, so the other models, ECMWF's AI model among them, get a verdict of their own once the checks are run again.

Every chart has a Table button with the same numbers, and the page follows the system light or dark setting. The footer carries the attribution Open-Meteo, NOAA, IEM and CHIRPS ask for; keep it if you restyle the page.

## End-to-end test

`tests/test_pipeline.py` drives the whole thing through the command line on synthetic data: `gnostiq all`, then `gnostiq run` with a stand-in for the live forecast, then the API, then a second site on the first site's networks. If a change breaks the wiring between two modules, this is the test that fails.

## Running it for real

After setting up with your tool as described under Setup:

### Standard Python (`venv` / `virtualenv`)

```
python scripts/gate.py                           # then change the keys it lists in gnostiq.toml
gnostiq pull                                     # everything; safe to re-run
gnostiq pull --only tamsat                       # optional: a second rain truth for the scorecard
gnostiq all                                      # build, baselines, train, verify, cases
gnostiq --site jos pull --only static,nwp,nimet  # Jos: terrain height, forecasts, reports
gnostiq season --all-sites                       # the latest wet season against NiMet reports, both sites
gnostiq run --all-sites                          # live forecast for Abuja and Jos
gnostiq serve                                    # http://127.0.0.1:8000
```

### uv

```
uv run python scripts/gate.py                           # then change the keys it lists in gnostiq.toml
uv run gnostiq pull                                     # everything; safe to re-run
uv run gnostiq pull --only tamsat                       # optional: a second rain truth for the scorecard
uv run gnostiq all                                      # build, baselines, train, verify, cases
uv run gnostiq --site jos pull --only static,nwp,nimet  # Jos: terrain height, forecasts, reports
uv run gnostiq season --all-sites                       # the latest wet season against NiMet reports, both sites
uv run gnostiq run --all-sites                          # live forecast for Abuja and Jos
uv run gnostiq serve                                    # http://127.0.0.1:8000
```

### Poetry

```
poetry run python scripts/gate.py                           # then change the keys it lists in gnostiq.toml
poetry run gnostiq pull                                     # everything; safe to re-run
poetry run gnostiq pull --only tamsat                       # optional: a second rain truth for the scorecard
poetry run gnostiq all                                      # build, baselines, train, verify, cases
poetry run gnostiq --site jos pull --only static,nwp,nimet  # Jos: terrain height, forecasts, reports
poetry run gnostiq season --all-sites                       # the latest wet season against NiMet reports, both sites
poetry run gnostiq run --all-sites                          # live forecast for Abuja and Jos
poetry run gnostiq serve                                    # http://127.0.0.1:8000
```

### Pipenv

```
pipenv run python scripts/gate.py                           # then change the keys it lists in gnostiq.toml
pipenv run gnostiq pull                                     # everything; safe to re-run
pipenv run gnostiq pull --only tamsat                       # optional: a second rain truth for the scorecard
pipenv run gnostiq all                                      # build, baselines, train, verify, cases
pipenv run gnostiq --site jos pull --only static,nwp,nimet  # Jos: terrain height, forecasts, reports
pipenv run gnostiq season --all-sites                       # the latest wet season against NiMet reports, both sites
pipenv run gnostiq run --all-sites                          # live forecast for Abuja and Jos
pipenv run gnostiq serve                                    # http://127.0.0.1:8000
```

### Hatch

```
hatch run python scripts/gate.py                           # then change the keys it lists in gnostiq.toml
hatch run gnostiq pull                                     # everything; safe to re-run
hatch run gnostiq pull --only tamsat                       # optional: a second rain truth for the scorecard
hatch run gnostiq all                                      # build, baselines, train, verify, cases
hatch run gnostiq --site jos pull --only static,nwp,nimet  # Jos: terrain height, forecasts, reports
hatch run gnostiq season --all-sites                       # the latest wet season against NiMet reports, both sites
hatch run gnostiq run --all-sites                          # live forecast for Abuja and Jos
hatch run gnostiq serve                                    # http://127.0.0.1:8000
```

### PDM

```
pdm run python scripts/gate.py                           # then change the keys it lists in gnostiq.toml
pdm run gnostiq pull                                     # everything; safe to re-run
pdm run gnostiq pull --only tamsat                       # optional: a second rain truth for the scorecard
pdm run gnostiq all                                      # build, baselines, train, verify, cases
pdm run gnostiq --site jos pull --only static,nwp,nimet  # Jos: terrain height, forecasts, reports
pdm run gnostiq season --all-sites                       # the latest wet season against NiMet reports, both sites
pdm run gnostiq run --all-sites                          # live forecast for Abuja and Jos
pdm run gnostiq serve                                    # http://127.0.0.1:8000
```

Read `data/abuja/reports/gate.md` first, then `qc.md`, then `scorecard.md` in the same directory, then `season.md` for both sites.

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

From your machine, copy the trained models, the reports and the terrain files:

```
rsync -a --relative data/abuja/models data/abuja/reports data/abuja/processed/static.json data/abuja/interim/obs.parquet \
    data/jos/processed/static.json <server>:/opt/gnostiq/app/
```

Then install the services from `deploy/`:

```
sudo cp deploy/gnostiq-*.service deploy/gnostiq-*.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now gnostiq-api.service gnostiq-run.timer gnostiq-check.timer
sudo systemctl start gnostiq-run.service     # first forecast now, not in three hours
```

The run timer refreshes the forecast for every site every three hours and saves each one under the site's `archive/`. The check timer scores those saved forecasts against new airport reports every morning; the first scores appear the day after the first forecast. `data/abuja/interim/obs.parquet` in the copy above is the station record the "normal for the date" range is computed from. For HTTPS, install Caddy and put your domain in `deploy/Caddyfile`.

To check it: `curl localhost:8000/api/health` shows when the forecast was issued, and `journalctl -u gnostiq-run` shows the last run.

To store each day's first forecast on Auto Drive (see Public record on Auto Drive), put the key where the run unit reads it:

```
echo 'AUTO_DRIVE_API_KEY=<key>' | sudo tee /etc/gnostiq.env
sudo chmod 600 /etc/gnostiq.env
```

The run unit publishes after every forecast; without the file it does a dry run. Records name the git commit; if `git` cannot read the checkout as the `gnostiq` user, add `GNOSTIQ_COMMIT=<sha>` to the same file. `journalctl -u gnostiq-run` shows each record's CID, and `data/<site>/reports/records.json` lists them all.

CI is in `.github/workflows/ci.yml`: lint and tests on every push and pull request. It installs without a lock file, so commit `uv.lock` and change the step to `uv sync --locked` once the stack is merged.

## Free hosting on GitHub

For when there is no server to pay for. The scheduled workflow `.github/workflows/live.yml` does the systemd timers' job: every three hours it makes a forecast for every site, publishes each day's first one to Auto Drive, scores past forecasts, and puts the page on GitHub Pages. It costs nothing for a public repository and needs no card.

The workflow's working files live on a branch called `state`: the trained networks, the reports, the terrain heights, the station record, the forecast archive and the list of published records. Each run checks the branch out as `data/`, works in it, and replaces it with a single new commit, so old forecasts never pile up in history.

Setting it up, once:

1. Train on your machine (Running it for real above), then commit and push the code.
2. Put the trained files on the `state` branch:
   ```
   uv run python scripts/seed_state.py
   ```
   It copies only what the workflow needs (`KEEP` in the script) and refuses to replace a `state` branch that already exists.
3. In the repository settings, under Pages, set Source to "GitHub Actions".
4. Under Settings, Secrets and variables, Actions, add `AUTO_DRIVE_API_KEY`. Without it, publishing is a dry run.
5. Under Actions, pick "live" and press "Run workflow". The page appears at `https://<user>.github.io/<repo>/`.

From then on, publish only from the workflow: leave `AUTO_DRIVE_API_KEY` unset on your machine, and never re-run the seed with `--force` after anything has been published, because the workflow's copy holds the record chain.

To put a season check run on your machine on the page, add its report to the branch:

```
uv run gnostiq season --all-sites --start 2026-04-01
uv run python scripts/seed_state.py --update reports/season.json reports/season.md
```

`--update` adds the named files on top of the branch the workflow keeps, rather than replacing it, and refuses anything outside what the workflow keeps. A run already under way when you push replaces the branch with its own copy; the script says to run it again in that case, and nothing else is lost. The page shows the new season after the next run.

To ship networks retrained on your machine, `--update models` does the same for the networks. By hand, change only `models/` on the branch:

```
git fetch origin state
git worktree add ../gnostiq-state origin/state
cp -r data/abuja/models ../gnostiq-state/abuja/
git -C ../gnostiq-state add -A
git -C ../gnostiq-state commit -m "state: retrained networks"
git -C ../gnostiq-state push origin HEAD:state
git worktree remove ../gnostiq-state
```

If the push is refused, a run replaced the branch in the meantime; remove the worktree and start again.

Things to know:

- Scheduled runs can start half an hour or more late when GitHub is busy. That is why the schedule is at 23 minutes past, not on the hour.
- GitHub switches off schedules in a public repository with no activity for 60 days. The workflow's own pushes should count as activity; if the Actions tab says "live" is disabled, enable it there.
- The page is static. It changes when a run finishes, not when someone visits; `serve` is not used.
- Every run's log is public and timestamped by GitHub, so each Auto Drive upload can be checked against a clock that is not yours.
- The trained networks and the archive are public on the `state` branch.
- `gnostiq export <dir>` writes the same page and reports as plain files, for any static host.

## Keeping it current

- The forecast refreshes itself through the timer.
- To extend training past the current test window: move the dates in `[window]`, run `gnostiq pull --refresh` then `gnostiq all` (with your tool's `run` prefix), and copy `data/models` and `data/reports` to the server again. Pick the new test window before you look at any scores for it.
- CHIRPS final data arrives around the third week of the following month. Until then recent days are preliminary, and `pull` replaces them when the final files appear.

## What has been checked, and what has not

The pipeline has run end to end on real data for Abuja, with the 2025 wet season as the test; the tests use synthetic data. Request formats were checked by hand in a browser on 2026-11-17 and 2026-11-19.

| Source | Checked | Result |
|---|---|---|
| Open-Meteo archive, `ecmwf_ifs025`, core variables | Yes | Works |
| Same, CAPE and column water vapour | Yes | Served but all null |
| Same, pressure-level fields | Yes | Refused by the API |
| `gfs_seamless` | Yes | Works, including CAPE |
| `icon_seamless` | Yes | Works at short leads; day 7 is null |
| AIFS, ARPEGE, JMA, GEM | Yes | Work; ARPEGE stops at day 4, AIFS starts in 2024 |
| CHIRPS v3 | Yes | Read for Abuja after the rate-limit fixes |
| NOAA GHCNh station list and data file | Yes | Parser fixed against a real file |
| IEM METARs | Yes | Works; Nigerian reports thin out from April 2026 |
| NiMet WIS2 node | Yes | Works from a cloud browser; timed out from one home connection |
| TAMSAT v3.1 | Partly | File names and sizes seen in the archive index; no file read yet |
| Auto Drive S3 upload and gateway | No | Built from Autonomys's documentation; not yet run with a key |
| GitHub Actions workflow and Pages | No | Not yet run on GitHub; the export and seed script are tested |

## Assumptions to check on real data

1. **GHCNh file layout.** See "Not yet checked against a real file" under Station observations. This is the most likely thing to need a fix on the first run, and the gate exercises it first.
2. **CHIRPS day boundary.** Daily totals are treated as 00 to 00 UTC. If the product's day is offset, forecast and truth are misaligned by some hours.
3. **Station identity.** If the gate says the synoptic and METAR temperatures come from a "different site or sensor", `truth.temp = "merged"` mixes two instruments. Use `ghcnh` or `iem` alone.
4. **Station height.** The terrain correction is station height minus the model's 1182 m. At the listed 1295 m the model is cooled by about 0.7 degC. If the gate's barometer estimate disagrees with 1295 m, fix the site's `elev_m` before training.
5. **Auto Drive CID.** `publish` reads the CID from the upload response's `x-amz-meta-cid` header, or `VersionId`. If the first real upload stops with "returned no CID", the response carries it elsewhere; nothing is lost, since the record is not written until the forecast's CID is known, but the forecast itself is already stored.
6. **Open-Meteo licence.** The free API is non-commercial. A commercial service needs their paid plan or your own ingest of ECMWF open data.

## Known gaps

- **No CAPE, column water vapour or pressure-level inputs.** The lead-time archive does not have them for ECMWF. The rain model's moisture supply is estimated from surface dewpoint, and the terrain correction uses the standard 6.5 K/km. Two ways to close this: use GFS CAPE as an extra predictor, since the archive has it, or pull whole ECMWF runs through Open-Meteo's Single Runs API, which is a bigger ingest job.
- **One verified site and one test season.** Jos runs Abuja's networks unverified until `gnostiq season` has scored it against NiMet's 2026 reports, and then only by day.
- **The IFS changed cycle on 12 May 2026**, inside the default test window. Training data comes from the earlier cycle.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `pull` stops with a 400 on the core group | Open-Meteo rejected a variable or the model id. The message quotes the server's reason. Fix the id in `gnostiq.toml` or the name in `GROUPS` in `ingest/nwp.py`. |
| Warning `variable group 'levels' not served` | Expected. A `levels.missing` marker stops further attempts; `--refresh` tries again. |
| 429 or repeated retries | Rate limit. Wait, then re-run; finished downloads are skipped. |
| `removed N unreadable forecast chunk(s)` from `gnostiq all` | A download came back empty or cut off. Run `gnostiq pull --only nwp`, which fetches just those chunks, then `gnostiq all`. |
| `N GHCNh candidates ...` | Several station records match. Run the gate and set the site's `ghcnh`. |
| CHIRPS log says many days not read | Usually the rate limit; re-run. If every read fails, open one URL from `precip.url()` in a browser. |
| `pairs have no train or no test rows` | The windows do not overlap the data. Check the last observation date in `data/reports/gate.md`. |
| `only N wet training days` | Rain truth is too sparse. Use `truth.rain = "chirps"`. |
| The page says "Not available yet" | The command it names has not been run, or `data/reports` was not copied to the server. |
