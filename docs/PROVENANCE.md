# Public forecast record on Auto Drive

Every forecast Gnostiq issues can be checked later against what happened, but only if the forecast shown later is the one actually issued. A copy kept on Gnostiq's own server proves nothing to anyone who does not trust that server. So the first forecast of each UTC day, the one the live check scores, is stored on Autonomys Auto Drive, where content is addressed by its hash and cannot be changed or removed once written. Anyone can fetch it and check it without Gnostiq.

## What is stored

For each site and day, two objects:

| Key | What | Size |
|---|---|---|
| `gnostiq/<site>/<day>/forecast.json.gz` | The forecast exactly as the page served it: seven days of hourly temperature and dewpoint quantiles, the raw and height-corrected model values, the other models, and daily rain chances. Gzipped with a fixed timestamp, so the same forecast always gives the same bytes and the same CID. | Up to about 13 KB (about 100 KB unpacked) |
| `gnostiq/<site>/<day>/record.json` | The record that ties it together | about 1.3 KB |

The record, schema `gnostiq.record/1`:

| Field | Meaning |
|---|---|
| `site` | Name, latitude, longitude, height |
| `issued_utc` | The forecast's initial time, as in the forecast itself |
| `published_utc` | When it was uploaded. Normally a few hours after `issued_utc`: the time for the model run to reach Open-Meteo, plus up to three hours to the next run. |
| `forecast.cid`, `forecast.sha256`, `forecast.bytes`, `forecast.stored_bytes` | The forecast's CID, the SHA-256 of the unpacked JSON, and both sizes |
| `model.trained_utc`, `model.trained_at` | When the networks were trained, and at which site (Jos runs Abuja's) |
| `model.hourly_sha256`, `model.daily_sha256` | Hashes of the trained network files that produced it |
| `code.version`, `code.commit` | Package version and git commit |
| `config_sha256` | Hash of `gnostiq.toml` |
| `sources.forecast` | The input model (`ecmwf_ifs025` through Open-Meteo) and the other models shown beside it |
| `sources.training` | Training window, and the temperature and rain truth it was trained against |
| `previous` | CID of the same site's record for the previous published day, or null for the first |

`previous` makes each site's records a chain. One CID, the latest, reaches every earlier record. A record cannot be edited without changing its CID, and the record after it still names the old one, so a rewrite of history shows.

## Architecture

| Command | When | What it does |
|---|---|---|
| `gnostiq run` | Every 3 hours | Writes the forecast, and keeps it in `archive/` as `<init>.parquet` for scoring and `<init>.json.gz` for publishing |
| `gnostiq publish` | After each run | Uploads each UTC day's first issue not yet stored, with its record |
| `gnostiq check` | Daily | Scores the archived first issues against NiMet and airport reports |
| `gnostiq serve` | Always | Serves `/api/<site>/records` and shows the latest record under the forecast |
| `gnostiq verify-record <cid>` | Anyone, any time | Fetches records from the gateway, checks their hashes, follows `previous` |

`publish` uses Auto Drive's S3-compatible endpoint, `https://s3.auto-drive.autonomys.xyz`, with the API key as the access key. It uploads the forecast, then the record naming the forecast's CID, then writes the site's `reports/records.json` (every record's day, issue time, both CIDs, hash and size, the latest CID, total bytes). That index is rewritten after each day, so a failure part way loses nothing already stored. A day missed because the server was down is caught up on the next run, up to three days back. Without `AUTO_DRIVE_API_KEY`, `publish` is a dry run and writes what it would have stored to `published/<day>.dry-run.json`.

Reading goes through the public gateway, `https://gateway.autonomys.xyz/file/<cid>`, and needs no account.

## Checking a record

With the package installed, nothing else:

```
gnostiq verify-record <cid>
gnostiq verify-record <cid> --depth 7
```

For each record back along the chain it fetches the record and its forecast, checks that the forecast hashes to `forecast.sha256`, and that it is for the issue time and site the record names. It prints one line per record and exits 1 if any fails.

Without Gnostiq at all:

```
curl -s https://gateway.autonomys.xyz/file/<record-cid>
curl -s https://gateway.autonomys.xyz/file/<forecast-cid> | gunzip | sha256sum
```

The hash must equal `forecast.sha256` in the record. If the gateway already unpacked the file, drop `gunzip`.

What a check proves: the forecast stored under that record is byte for byte what Gnostiq published, and was on Auto Drive by the time the next record was. What it does not prove by itself: that `published_utc` is true. The chain and the network's own timestamps bound it; anyone who wants to rely on it can fetch the latest CID from the page each day and keep it.

## Storage used

Measured on a full seven-day forecast with the six models now shown, the forecast packs to about 13 KB and its record is about 1.3 KB, so roughly 14 KB per site per day.

| | Per month | Per year |
|---|---|---|
| 2 sites (Abuja, Jos), first issue per day | 0.9 MB | 10 MB |
| 7 sites, first issue per day | 3 MB | 36 MB |
| 2 sites, every issue (8 a day) | 7 MB | 82 MB |
| 7 sites, every issue | 24 MB | 290 MB |

The free tier allows 20 MB of uploads and 5 GB of downloads a month. Two sites, or the seven-state pilot, at one forecast per day fit with room to spare. Storing every issue, which would let the live check score every forecast rather than one a day, fits for two sites and not for seven. Each verification of a whole year for one site downloads about 5 MB.

## What comes next

- Publish every issue, not only the first per day, once there is storage for it: about 24 MB a month for seven sites.
- Add the scores: a monthly record of the live check, naming the forecast CIDs it scored, so a skill claim can be traced to the stored forecasts behind it.
- Store the trained network files once per training, a one-off upload the size of `models/`, and name their CIDs in the records instead of only their hashes, so anyone can rerun a forecast from its stored inputs.
