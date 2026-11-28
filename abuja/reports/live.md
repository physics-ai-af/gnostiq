# Live check: abuja

Forecasts as the page showed them, first issue of each UTC day, scored against station reports from 2026-10-29 to 2026-11-28T08:00Z: NiMet synops (0.1 C) where they exist, airport METARs (whole degrees) otherwise.

Skill is 1 - CRPS/reference; brackets are 95% intervals from resampling whole days. Raw models are scored as single values, so their CRPS is their absolute error.

9 days of forecasts, 421 reports.

## t2m (817 cases)

| system | n | bias | MAE | CRPS |
|---|---|---|---|---|
| clim | 817 | -2.34 | 2.39 | 1.64 |
| gnostiq | 817 | -0.47 | 0.80 | 0.56 |
| lapse | 817 | -0.78 | 1.15 | 1.15 |
| raw | 817 | -0.68 | 1.10 | 1.10 |
| raw:ecmwf_aifs025_single | 718 | +0.07 | 1.02 | 1.02 |
| raw:gem_global | 718 | +0.15 | 1.10 | 1.10 |
| raw:gfs_seamless | 817 | +0.85 | 1.31 | 1.31 |
| raw:icon_seamless | 817 | -1.10 | 1.42 | 1.42 |
| raw:jma_gsm | 718 | -0.31 | 2.05 | 2.05 |
| raw:meteofrance_arpege_world | 501 | +0.42 | 1.17 | 1.17 |

CRPSS vs raw: +0.494 [+0.445, +0.535]
CRPSS vs lapse: +0.516 [+0.462, +0.556]
CRPSS vs clim: +0.663 [+0.598, +0.693]
CRPSS vs raw:ecmwf_aifs025_single: +0.454 [+0.363, +0.555]
CRPSS vs raw:gem_global: +0.492 [+0.411, +0.570]
CRPSS vs raw:gfs_seamless: +0.577 [+0.511, +0.648]
CRPSS vs raw:icon_seamless: +0.608 [+0.561, +0.680]
CRPSS vs raw:jma_gsm: +0.728 [+0.690, +0.751]
CRPSS vs raw:meteofrance_arpege_world: +0.511 [+0.438, +0.567]

## td2m (817 cases)

| system | n | bias | MAE | CRPS |
|---|---|---|---|---|
| clim | 817 | -2.10 | 2.97 | 1.93 |
| gnostiq | 817 | -1.84 | 2.17 | 1.49 |
| lapse | 817 | -3.63 | 3.75 | 3.75 |
| raw | 817 | -3.63 | 3.75 | 3.75 |
| raw:ecmwf_aifs025_single | 718 | -3.59 | 3.69 | 3.69 |
| raw:gem_global | 718 | -6.49 | 6.57 | 6.57 |
| raw:gfs_seamless | 817 | -6.38 | 6.40 | 6.40 |
| raw:icon_seamless | 817 | -0.18 | 1.43 | 1.43 |
| raw:jma_gsm | 718 | -2.18 | 2.32 | 2.32 |
| raw:meteofrance_arpege_world | 501 | -4.31 | 4.41 | 4.41 |

CRPSS vs raw: +0.603 [+0.539, +0.685]
CRPSS vs lapse: +0.603 [+0.536, +0.682]
CRPSS vs clim: +0.229 [+0.067, +0.389]
CRPSS vs raw:ecmwf_aifs025_single: +0.586 [+0.520, +0.685]
CRPSS vs raw:gem_global: +0.767 [+0.721, +0.842]
CRPSS vs raw:gfs_seamless: +0.767 [+0.729, +0.813]
CRPSS vs raw:icon_seamless: -0.044 [-0.487, +0.368]
CRPSS vs raw:jma_gsm: +0.341 [-0.011, +0.607]
CRPSS vs raw:meteofrance_arpege_world: +0.658 [+0.600, +0.736]

## Track record: 10 days, day-ahead forecast as the page showed it

High from 11:00 to 17:00 and low from 04:00 to 08:00 local time, over the hours reported (at least 2 in each).

- High, gnostiq: average error 0.51 C, within 1 C on 100% of 7 days
- High, raw: average error 1.41 C, within 1 C on 29% of 7 days
- Low, gnostiq: average error 0.73 C, within 1 C on 71% of 7 days
- Low, raw: average error 1.10 C, within 1 C on 43% of 7 days
- Reports inside Gnostiq's 80% range: 110 of 127 hours (87%)

## Last 7 days, day-ahead forecast against reports

- t2m: report inside Gnostiq's 80% range 102 of 119 times (expect about 80%)
- td2m: report inside Gnostiq's 80% range 71 of 119 times (expect about 80%)

Highs and lows over the reported hours (Africa/Lagos days):

| day | hours | reported | Gnostiq | raw |
|---|---|---|---|---|
| 2026-11-21 | 5 | 35.0 / None | 34.8 / None | 33.5 / None |
| 2026-11-23 | 14 | 36.0 / 21.5 | 35.1 / 21.2 | 34.4 / 22.3 |
| 2026-11-24 | 19 | 36.5 / 21.6 | 36.7 / 21.5 | 35.3 / 22.8 |
| 2026-11-25 | 24 | 35.3 / 21.8 | 35.9 / 21.4 | 34.0 / 23.7 |
| 2026-11-26 | 22 | 35.5 / 22.3 | 35.9 / 21.7 | 34.6 / 23.3 |
| 2026-11-27 | 24 | 35.5 / 23.7 | 36.1 / 22.0 | 34.7 / 23.5 |
