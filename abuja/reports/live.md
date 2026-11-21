# Live check: abuja

Forecasts as the page showed them, first issue of each UTC day, scored against station reports from 2026-10-22 to 2026-11-21T07:00Z: NiMet synops (0.1 C) where they exist, airport METARs (whole degrees) otherwise.

Skill is 1 - CRPS/reference; brackets are 95% intervals from resampling whole days. Raw models are scored as single values, so their CRPS is their absolute error.

3 days of forecasts, 440 reports.

## t2m (31 cases)

| system | n | bias | MAE | CRPS |
|---|---|---|---|---|
| clim | 31 | -0.69 | 1.32 | 1.06 |
| gnostiq | 31 | -0.43 | 0.70 | 0.47 |
| lapse | 31 | +0.21 | 1.28 | 1.28 |
| raw | 31 | +0.31 | 1.31 | 1.31 |
| raw:ecmwf_aifs025_single | 10 | +0.51 | 1.87 | 1.87 |
| raw:gem_global | 10 | -0.22 | 0.44 | 0.44 |
| raw:gfs_seamless | 31 | +1.14 | 1.78 | 1.78 |
| raw:icon_seamless | 31 | -3.23 | 3.31 | 3.31 |
| raw:jma_gsm | 10 | +0.50 | 2.34 | 2.34 |
| raw:meteofrance_arpege_world | 10 | +0.32 | 1.36 | 1.36 |

CRPSS vs raw: -
CRPSS vs lapse: -
CRPSS vs clim: -
CRPSS vs raw:ecmwf_aifs025_single: -
CRPSS vs raw:gem_global: -
CRPSS vs raw:gfs_seamless: -
CRPSS vs raw:icon_seamless: -
CRPSS vs raw:jma_gsm: -
CRPSS vs raw:meteofrance_arpege_world: -

## td2m (31 cases)

| system | n | bias | MAE | CRPS |
|---|---|---|---|---|
| clim | 31 | +2.51 | 2.67 | 1.89 |
| gnostiq | 31 | +0.15 | 0.97 | 0.77 |
| lapse | 31 | -2.99 | 3.02 | 3.02 |
| raw | 31 | -2.99 | 3.02 | 3.02 |
| raw:ecmwf_aifs025_single | 10 | -3.26 | 4.04 | 4.04 |
| raw:gem_global | 10 | -10.16 | 10.16 | 10.16 |
| raw:gfs_seamless | 31 | -7.47 | 7.47 | 7.47 |
| raw:icon_seamless | 31 | -1.88 | 2.16 | 2.16 |
| raw:jma_gsm | 10 | -4.36 | 4.36 | 4.36 |
| raw:meteofrance_arpege_world | 10 | -6.13 | 6.51 | 6.51 |

CRPSS vs raw: -
CRPSS vs lapse: -
CRPSS vs clim: -
CRPSS vs raw:ecmwf_aifs025_single: -
CRPSS vs raw:gem_global: -
CRPSS vs raw:gfs_seamless: -
CRPSS vs raw:icon_seamless: -
CRPSS vs raw:jma_gsm: -
CRPSS vs raw:meteofrance_arpege_world: -

## Track record: 3 days, day-ahead forecast as the page showed it

High from 11:00 to 17:00 and low from 04:00 to 08:00 local time, over the hours reported (at least 2 in each).

- High, gnostiq: average error 0.70 C, within 1 C on 100% of 1 days
- High, raw: average error 2.60 C, within 1 C on 0% of 1 days
- Low, gnostiq: average error 1.00 C, within 1 C on 50% of 2 days
- Low, raw: average error 1.30 C, within 1 C on 0% of 2 days
- Reports inside Gnostiq's 80% range: 8 of 8 hours (100%)

## Last 7 days, day-ahead forecast against reports

- t2m: report inside Gnostiq's 80% range 13 of 14 times (expect about 80%)
- td2m: report inside Gnostiq's 80% range 12 of 14 times (expect about 80%)

Highs and lows over the reported hours (Africa/Lagos days):

| day | hours | reported | Gnostiq | raw |
|---|---|---|---|---|
| 2026-11-19 | 6 | None / 22.5 | None / 21.6 | None / 23.9 |
| 2026-11-20 | 6 | 37.0 / None | 36.3 / None | 34.4 / None |
| 2026-11-21 | 2 | None / 21.0 | None / 19.9 | None / 22.2 |
