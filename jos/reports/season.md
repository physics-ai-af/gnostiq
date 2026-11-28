# Season: jos, 2026-04-01 to 2026-10-31

What each system would have issued from the archived forecasts, scored against NiMet synops from 0-20000-0-65134 (9.867 N 8.900 E, 25.5 km from the site). Networks trained at abuja up to 2025-03-31; nothing here was seen in training.

622 reports. Hours scored (UTC): 01 (1), 04 (1), 05 (7), 06 (41), 07 (42), 08 (59), 09 (49), 10 (61), 11 (65), 12 (57), 13 (62), 14 (61), 15 (47), 16 (45), 17 (20), 18 (4)

Skill is 1 - CRPS/reference with 95% intervals from resampling whole days. Raw models are single values, so their CRPS is their absolute error.

## t2m (4342 cases)

| system | n | bias | MAE | CRPS |
|---|---|---|---|---|
| emos | 4342 | +0.47 | 1.50 | 1.10 |
| emos_multi | 4342 | +0.74 | 1.45 | 1.07 |
| gnostiq | 4342 | +1.88 | 2.09 | 1.61 |
| lapse | 4342 | -0.49 | 1.59 | 1.59 |
| raw | 4342 | -0.02 | 1.53 | 1.53 |
| raw:ecmwf_aifs025_single | 4279 | -0.16 | 1.43 | 1.43 |
| raw:gem_global | 4342 | +0.01 | 1.83 | 1.83 |
| raw:gfs_seamless | 4342 | +0.15 | 1.83 | 1.83 |
| raw:icon_seamless | 3660 | +0.04 | 1.45 | 1.45 |
| raw:jma_gsm | 4252 | +0.24 | 1.56 | 1.56 |
| raw:meteofrance_arpege_world | 1826 | -0.11 | 1.72 | 1.72 |

CRPSS vs raw: -0.058 [-0.158, +0.051]
CRPSS vs lapse: -0.015 [-0.123, +0.096]
CRPSS vs emos: -0.473 [-0.580, -0.369]
CRPSS vs emos_multi: -0.502 [-0.583, -0.422]

CRPS by lead day:

| system | day 1 | day 2 | day 3 | day 4 | day 5 | day 6 | day 7 |
|---|---|---|---|---|---|---|---|
| emos | 0.96 | 1.04 | 1.09 | 1.10 | 1.13 | 1.15 | 1.19 |
| emos_multi | 0.95 | 1.04 | 1.07 | 1.09 | 1.09 | 1.14 | 1.14 |
| gnostiq | 1.60 | 1.64 | 1.60 | 1.65 | 1.64 | 1.57 | 1.60 |
| lapse | 1.45 | 1.50 | 1.53 | 1.56 | 1.58 | 1.68 | 1.83 |
| raw | 1.37 | 1.46 | 1.50 | 1.53 | 1.54 | 1.57 | 1.69 |
| raw:ecmwf_aifs025_single | 1.27 | 1.41 | 1.40 | 1.48 | 1.48 | 1.45 | 1.51 |
| raw:gem_global | 1.75 | 1.73 | 1.89 | 1.88 | 1.78 | 1.86 | 1.96 |
| raw:gfs_seamless | 1.83 | 1.87 | 1.76 | 1.76 | 1.79 | 1.89 | 1.92 |
| raw:icon_seamless | 1.34 | 1.39 | 1.43 | 1.47 | 1.52 | 1.53 | - |
| raw:jma_gsm | 1.46 | 1.59 | 1.56 | 1.57 | 1.57 | 1.55 | 1.62 |
| raw:meteofrance_arpege_world | 1.60 | 1.73 | 1.83 | - | - | - | - |

## td2m (4342 cases)

| system | n | bias | MAE | CRPS |
|---|---|---|---|---|
| emos | 4342 | +2.04 | 2.33 | 1.77 |
| emos_multi | 4342 | +1.52 | 1.95 | 1.50 |
| gnostiq | 4342 | +0.97 | 1.74 | 1.32 |
| lapse | 4342 | -1.19 | 1.94 | 1.94 |
| raw | 4342 | -1.06 | 1.88 | 1.88 |
| raw:ecmwf_aifs025_single | 4237 | -0.40 | 1.75 | 1.75 |
| raw:gem_global | 4332 | -0.20 | 1.99 | 1.99 |
| raw:gfs_seamless | 4342 | -2.57 | 3.00 | 3.00 |
| raw:icon_seamless | 3648 | -0.17 | 1.67 | 1.67 |
| raw:jma_gsm | 4204 | -1.14 | 2.20 | 2.20 |
| raw:meteofrance_arpege_world | 1798 | +1.26 | 2.37 | 2.37 |

CRPSS vs raw: +0.300 [+0.179, +0.409]
CRPSS vs lapse: +0.321 [+0.203, +0.423]
CRPSS vs emos: +0.257 [+0.208, +0.305]
CRPSS vs emos_multi: +0.118 [+0.043, +0.181]

CRPS by lead day:

| system | day 1 | day 2 | day 3 | day 4 | day 5 | day 6 | day 7 |
|---|---|---|---|---|---|---|---|
| emos | 1.78 | 1.68 | 1.79 | 1.68 | 1.75 | 1.84 | 1.89 |
| emos_multi | 1.36 | 1.39 | 1.51 | 1.46 | 1.48 | 1.56 | 1.71 |
| gnostiq | 1.25 | 1.21 | 1.33 | 1.29 | 1.33 | 1.38 | 1.45 |
| lapse | 1.70 | 1.85 | 1.80 | 1.94 | 1.86 | 2.12 | 2.34 |
| raw | 1.64 | 1.78 | 1.74 | 1.88 | 1.80 | 2.06 | 2.29 |
| raw:ecmwf_aifs025_single | 1.56 | 1.95 | 2.01 | 1.70 | 1.57 | 1.74 | 1.72 |
| raw:gem_global | 2.21 | 1.95 | 1.89 | 2.05 | 1.77 | 2.02 | 2.04 |
| raw:gfs_seamless | 3.33 | 3.26 | 2.86 | 2.74 | 2.94 | 2.91 | 2.96 |
| raw:icon_seamless | 1.63 | 1.62 | 1.66 | 1.56 | 1.73 | 1.84 | - |
| raw:jma_gsm | 2.22 | 2.19 | 2.08 | 2.06 | 2.25 | 2.23 | 2.37 |
| raw:meteofrance_arpege_world | 2.17 | 2.32 | 2.63 | - | - | - | - |
