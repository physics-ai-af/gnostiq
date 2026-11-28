# Live check: jos

Forecasts as the page showed them, first issue of each UTC day, scored against station reports from 2026-10-29 to 2026-11-28T08:00Z: NiMet synops (0.1 C) where they exist, airport METARs (whole degrees) otherwise.

Skill is 1 - CRPS/reference; brackets are 95% intervals from resampling whole days. Raw models are scored as single values, so their CRPS is their absolute error.

10 days of forecasts, 68 reports.

## t2m (179 cases)

| system | n | bias | MAE | CRPS |
|---|---|---|---|---|
| gnostiq | 179 | +2.01 | 2.02 | 1.55 |
| lapse | 179 | +0.44 | 1.23 | 1.23 |
| raw | 179 | +0.94 | 1.45 | 1.45 |
| raw:ecmwf_aifs025_single | 170 | +0.32 | 1.29 | 1.29 |
| raw:gem_global | 170 | +2.31 | 2.31 | 2.31 |
| raw:gfs_seamless | 179 | +0.59 | 1.11 | 1.11 |
| raw:icon_seamless | 179 | +1.14 | 1.26 | 1.26 |
| raw:jma_gsm | 170 | -0.35 | 1.44 | 1.44 |
| raw:meteofrance_arpege_world | 96 | +1.67 | 1.71 | 1.71 |

CRPSS vs raw: -0.067 [-0.613, +0.366]
CRPSS vs lapse: -0.256 [-1.138, +0.321]
CRPSS vs raw:ecmwf_aifs025_single: -0.179 [-1.155, +0.355]
CRPSS vs raw:gem_global: +0.342 [+0.223, +0.439]
CRPSS vs raw:gfs_seamless: -0.389 [-1.756, +0.286]
CRPSS vs raw:icon_seamless: -0.224 [-0.538, +0.085]
CRPSS vs raw:jma_gsm: -0.058 [-0.640, +0.199]
CRPSS vs raw:meteofrance_arpege_world: +0.139 [-0.043, +0.363]

## td2m (179 cases)

| system | n | bias | MAE | CRPS |
|---|---|---|---|---|
| gnostiq | 179 | +1.29 | 1.95 | 1.42 |
| lapse | 179 | -4.55 | 4.60 | 4.60 |
| raw | 179 | -4.45 | 4.51 | 4.51 |
| raw:ecmwf_aifs025_single | 170 | -0.94 | 1.60 | 1.60 |
| raw:gem_global | 170 | -7.04 | 7.04 | 7.04 |
| raw:gfs_seamless | 179 | -6.21 | 6.36 | 6.36 |
| raw:icon_seamless | 179 | -2.82 | 3.37 | 3.37 |
| raw:jma_gsm | 170 | -4.28 | 4.84 | 4.84 |
| raw:meteofrance_arpege_world | 96 | -5.45 | 5.48 | 5.48 |

CRPSS vs raw: +0.685 [+0.215, +0.800]
CRPSS vs lapse: +0.692 [+0.267, +0.804]
CRPSS vs raw:ecmwf_aifs025_single: +0.125 [-1.016, +0.476]
CRPSS vs raw:gem_global: +0.801 [+0.565, +0.880]
CRPSS vs raw:gfs_seamless: +0.777 [+0.475, +0.859]
CRPSS vs raw:icon_seamless: +0.579 [-0.112, +0.739]
CRPSS vs raw:jma_gsm: +0.711 [+0.279, +0.816]
CRPSS vs raw:meteofrance_arpege_world: +0.747 [+0.433, +0.841]

## Track record: 5 days, day-ahead forecast as the page showed it

High from 11:00 to 17:00 and low from 04:00 to 08:00 local time, over the hours reported (at least 2 in each).

- High, gnostiq: average error 1.30 C, within 1 C on 33% of 3 days
- High, raw: average error 0.60 C, within 1 C on 100% of 3 days
- Low, gnostiq: average error 4.00 C, within 1 C on 0% of 1 days
- Low, raw: average error 5.00 C, within 1 C on 0% of 1 days
- Reports inside Gnostiq's 80% range: 9 of 21 hours (43%)

## Last 7 days, day-ahead forecast against reports

- t2m: report inside Gnostiq's 80% range 9 of 21 times (expect about 80%)
- td2m: report inside Gnostiq's 80% range 16 of 21 times (expect about 80%)

Highs and lows over the reported hours (Africa/Lagos days):

| day | hours | reported | Gnostiq | raw |
|---|---|---|---|---|
| 2026-11-25 | 7 | 30.5 / None | 32.0 / None | 30.9 / None |
| 2026-11-26 | 5 | 31.4 / 14.5 | 32.1 / 18.5 | 31.0 / 19.5 |
| 2026-11-27 | 8 | 30.5 / None | 32.2 / None | 31.5 / None |
