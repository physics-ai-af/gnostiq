# Live check: jos

Forecasts as the page showed them, first issue of each UTC day, scored against station reports from 2026-10-22 to 2026-11-21T07:00Z: NiMet synops (0.1 C) where they exist, airport METARs (whole degrees) otherwise.

Skill is 1 - CRPS/reference; brackets are 95% intervals from resampling whole days. Raw models are scored as single values, so their CRPS is their absolute error.

4 days of forecasts, 70 reports.

## t2m (2 cases)

| system | n | bias | MAE | CRPS |
|---|---|---|---|---|
| gnostiq | 2 | +3.35 | 3.35 | 2.73 |
| lapse | 2 | +4.60 | 4.60 | 4.60 |
| raw | 2 | +5.10 | 5.10 | 5.10 |
| raw:ecmwf_aifs025_single | 1 | +4.70 | 4.70 | 4.70 |
| raw:gem_global | 1 | +2.50 | 2.50 | 2.50 |
| raw:gfs_seamless | 2 | +2.80 | 2.80 | 2.80 |
| raw:icon_seamless | 2 | +1.00 | 1.00 | 1.00 |
| raw:jma_gsm | 1 | +4.40 | 4.40 | 4.40 |
| raw:meteofrance_arpege_world | 1 | +5.30 | 5.30 | 5.30 |

CRPSS vs raw: -
CRPSS vs lapse: -
CRPSS vs raw:ecmwf_aifs025_single: -
CRPSS vs raw:gem_global: -
CRPSS vs raw:gfs_seamless: -
CRPSS vs raw:icon_seamless: -
CRPSS vs raw:jma_gsm: -
CRPSS vs raw:meteofrance_arpege_world: -

## td2m (2 cases)

| system | n | bias | MAE | CRPS |
|---|---|---|---|---|
| gnostiq | 2 | +1.20 | 1.20 | 0.80 |
| lapse | 2 | -5.20 | 5.20 | 5.20 |
| raw | 2 | -5.10 | 5.10 | 5.10 |
| raw:ecmwf_aifs025_single | 1 | -2.30 | 2.30 | 2.30 |
| raw:gem_global | 1 | -6.40 | 6.40 | 6.40 |
| raw:gfs_seamless | 2 | -6.40 | 6.40 | 6.40 |
| raw:icon_seamless | 2 | -4.20 | 4.20 | 4.20 |
| raw:jma_gsm | 1 | -7.30 | 7.30 | 7.30 |
| raw:meteofrance_arpege_world | 1 | -5.00 | 5.00 | 5.00 |

CRPSS vs raw: -
CRPSS vs lapse: -
CRPSS vs raw:ecmwf_aifs025_single: -
CRPSS vs raw:gem_global: -
CRPSS vs raw:gfs_seamless: -
CRPSS vs raw:icon_seamless: -
CRPSS vs raw:jma_gsm: -
CRPSS vs raw:meteofrance_arpege_world: -

## Track record: 1 days, day-ahead forecast as the page showed it

High from 11:00 to 17:00 and low from 04:00 to 08:00 local time, over the hours reported (at least 2 in each).


## Last 7 days, day-ahead forecast against reports

- t2m: report inside Gnostiq's 80% range 0 of 1 times (expect about 80%)
- td2m: report inside Gnostiq's 80% range 1 of 1 times (expect about 80%)
