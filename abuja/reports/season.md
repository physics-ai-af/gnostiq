# Season: abuja, 2026-04-01 to 2026-10-31

What each system would have issued from the archived forecasts, scored against NiMet synops from 0-20000-0-65125 (9.020 N 7.275 E, 2.0 km from the site). Networks trained at abuja up to 2025-03-31; nothing here was seen in training.

2502 reports. Hours scored (UTC): 00 (93), 01 (101), 02 (97), 03 (95), 04 (94), 05 (99), 06 (101), 07 (96), 08 (97), 09 (91), 10 (92), 11 (101), 12 (111), 13 (117), 14 (120), 15 (122), 16 (119), 17 (123), 18 (123), 19 (102), 20 (106), 21 (104), 22 (103), 23 (95)

Skill is 1 - CRPS/reference with 95% intervals from resampling whole days. Raw models are single values, so their CRPS is their absolute error.

## t2m (17454 cases)

| system | n | bias | MAE | CRPS |
|---|---|---|---|---|
| clim | 17454 | -0.35 | 1.43 | 1.02 |
| emos | 17454 | -0.33 | 1.32 | 0.95 |
| emos_multi | 17454 | +0.17 | 1.19 | 0.88 |
| gnostiq | 17454 | -0.15 | 1.20 | 0.86 |
| lapse | 17454 | -1.08 | 1.67 | 1.67 |
| raw | 17454 | -0.93 | 1.59 | 1.59 |
| raw:ecmwf_aifs025_single | 17100 | -0.20 | 1.20 | 1.20 |
| raw:gem_global | 17350 | -0.89 | 2.00 | 2.00 |
| raw:gfs_seamless | 17454 | -1.25 | 1.99 | 1.99 |
| raw:icon_seamless | 14867 | -0.08 | 1.40 | 1.40 |
| raw:jma_gsm | 17085 | -1.13 | 1.83 | 1.83 |
| raw:meteofrance_arpege_world | 7399 | -0.24 | 1.67 | 1.67 |

CRPSS vs raw: +0.460 [+0.427, +0.490]
CRPSS vs lapse: +0.488 [+0.457, +0.516]
CRPSS vs emos: +0.095 [+0.066, +0.124]
CRPSS vs emos_multi: +0.025 [-0.006, +0.056]
CRPSS vs clim: +0.163 [+0.120, +0.200]

CRPS by lead day:

| system | day 1 | day 2 | day 3 | day 4 | day 5 | day 6 | day 7 |
|---|---|---|---|---|---|---|---|
| clim | 1.02 | 1.02 | 1.02 | 1.02 | 1.02 | 1.02 | 1.02 |
| emos | 0.93 | 0.93 | 0.94 | 0.92 | 0.95 | 0.97 | 0.98 |
| emos_multi | 0.82 | 0.85 | 0.86 | 0.87 | 0.89 | 0.89 | 0.96 |
| gnostiq | 0.81 | 0.82 | 0.84 | 0.86 | 0.86 | 0.87 | 0.93 |
| lapse | 1.56 | 1.60 | 1.65 | 1.60 | 1.66 | 1.77 | 1.84 |
| raw | 1.48 | 1.52 | 1.57 | 1.52 | 1.57 | 1.68 | 1.75 |
| raw:ecmwf_aifs025_single | 1.13 | 1.15 | 1.18 | 1.24 | 1.25 | 1.24 | 1.25 |
| raw:gem_global | 1.80 | 1.94 | 2.07 | 2.05 | 2.01 | 2.02 | 2.08 |
| raw:gfs_seamless | 1.73 | 1.92 | 1.97 | 1.98 | 2.12 | 2.04 | 2.16 |
| raw:icon_seamless | 1.27 | 1.35 | 1.40 | 1.46 | 1.47 | 1.44 | - |
| raw:jma_gsm | 1.74 | 1.77 | 1.81 | 1.80 | 1.82 | 1.92 | 1.96 |
| raw:meteofrance_arpege_world | 1.61 | 1.68 | 1.73 | - | - | - | - |

## td2m (17454 cases)

| system | n | bias | MAE | CRPS |
|---|---|---|---|---|
| clim | 17454 | -0.24 | 1.08 | 0.75 |
| emos | 17454 | +0.10 | 1.00 | 0.73 |
| emos_multi | 17454 | +0.16 | 0.93 | 0.69 |
| gnostiq | 17454 | +0.41 | 0.95 | 0.69 |
| lapse | 17454 | -0.44 | 1.07 | 1.07 |
| raw | 17454 | -0.40 | 1.05 | 1.05 |
| raw:ecmwf_aifs025_single | 16864 | -0.69 | 1.11 | 1.11 |
| raw:gem_global | 17312 | -0.76 | 1.44 | 1.44 |
| raw:gfs_seamless | 17454 | -1.54 | 1.76 | 1.76 |
| raw:icon_seamless | 14850 | +0.19 | 1.00 | 1.00 |
| raw:jma_gsm | 16899 | -1.00 | 1.39 | 1.39 |
| raw:meteofrance_arpege_world | 7352 | +0.38 | 1.31 | 1.31 |

CRPSS vs raw: +0.349 [+0.305, +0.395]
CRPSS vs lapse: +0.359 [+0.315, +0.402]
CRPSS vs emos: +0.058 [+0.011, +0.103]
CRPSS vs emos_multi: -0.001 [-0.043, +0.043]
CRPSS vs clim: +0.082 [+0.006, +0.148]

CRPS by lead day:

| system | day 1 | day 2 | day 3 | day 4 | day 5 | day 6 | day 7 |
|---|---|---|---|---|---|---|---|
| clim | 0.74 | 0.75 | 0.75 | 0.75 | 0.75 | 0.75 | 0.75 |
| emos | 0.74 | 0.72 | 0.71 | 0.72 | 0.72 | 0.73 | 0.74 |
| emos_multi | 0.70 | 0.69 | 0.67 | 0.68 | 0.67 | 0.68 | 0.70 |
| gnostiq | 0.72 | 0.70 | 0.68 | 0.68 | 0.67 | 0.68 | 0.68 |
| lapse | 1.06 | 1.08 | 1.08 | 1.08 | 1.06 | 1.05 | 1.06 |
| raw | 1.05 | 1.07 | 1.06 | 1.06 | 1.05 | 1.04 | 1.05 |
| raw:ecmwf_aifs025_single | 1.01 | 1.20 | 1.14 | 1.09 | 1.11 | 1.13 | 1.10 |
| raw:gem_global | 1.54 | 1.51 | 1.51 | 1.50 | 1.34 | 1.35 | 1.29 |
| raw:gfs_seamless | 1.83 | 1.81 | 1.73 | 1.74 | 1.75 | 1.75 | 1.75 |
| raw:icon_seamless | 0.99 | 1.03 | 0.99 | 1.01 | 1.00 | 0.99 | - |
| raw:jma_gsm | 1.58 | 1.40 | 1.35 | 1.30 | 1.33 | 1.36 | 1.39 |
| raw:meteofrance_arpege_world | 1.35 | 1.30 | 1.27 | - | - | - | - |
