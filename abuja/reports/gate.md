# Station data gate

Window 2021-01-01 to 2025-10-31; training ends 2025-03-31; test season 2025-04-01 to 2025-10-31.

## GHCNh records near the site

| id | lat | lon | elev | rest | wmo |
|---|---|---|---|---|---|
| NII0000DNAA | 9.01 | 7.26 | 342.30 | NNAMDI AZIKIWE INTL NG | False |
| NIM00065125 | 9.25 | 7.00 | 344.00 | ABUJA 65125 NG | True |

## GHCNh NII0000DNAA

Location history (a change mid-record means the station moved):

| LATITUDE | LONGITUDE | ELEVATION | min | max | count |
|---|---|---|---|---|---|
| 9.0068 | 7.2632 | 342.3 | 2021-01-01 00:00:00 | 2026-11-14 15:00:00 | 37603 |

Temperature report types:

| temperature_Report_Type | rows |
|---|---|
| FM15 | 37521 |
| (blank) | 82 |

Temperature QC codes (non-good codes are dropped):

| temperature_Quality_Code | rows |
|---|---|
| 1 | 36290 |
| (blank) | 907 |
| 4 | 315 |
| 2 | 90 |
| 3 | 1 |

### NII0000DNAA: temperature and dewpoint

- training months with synoptic coverage >= 80%: 43% (need 75%)
- test-season days with derivable Tmax/Tmin: 85% (need 85%)
- longest unusable run in test season: 6 days (max 21)
- last valid observation: 2026-11-14 15:00:00
- verdict: FAIL

Monthly synoptic-slot coverage, %:

| year | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2021 | 62 | 62 | 65 | 64 | 69 | 55 | 80 | 73 | 73 | 66 | 58 | 60 |
| 2022 | 60 | 56 | 61 | 68 | 56 | 65 | 40 | 81 | 75 | 83 | 89 | 92 |
| 2023 | 88 | 80 | 79 | 82 | 85 | 82 | 87 | 81 | 58 | 75 | 77 | 72 |
| 2024 | 79 | 77 | 90 | 82 | 84 | 80 | 90 | 89 | 84 | 88 | 87 | 77 |
| 2025 | 81 | 69 | 85 | 82 | 83 | 79 | 79 | 91 | 79 | 83 | - | - |

Share of days with an observation at each UTC hour, %:

| UTC hour | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 | 19 | 20 | 21 | 22 | 23 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train | 68 | 77 | 76 | 68 | 82 | 82 | 76 | 84 | 86 | 78 | 83 | 84 | 75 | 85 | 84 | 77 | 84 | 81 | 76 | 85 | 84 | 77 | 82 | 78 |
| test | 84 | 81 | 84 | 82 | 85 | 82 | 84 | 85 | 82 | 80 | 77 | 76 | 81 | 79 | 71 | 82 | 81 | 81 | 82 | 84 | 83 | 85 | 84 | 82 |

### NII0000DNAA: rain

- training wet-season days with a 24 h total: 0% (need 70%)
- test wet-season days with a 24 h total: 0% (need 80%)
- share of derivable days that are explicit zeros: -%
- verdict: FAIL

Annual totals (compare against CHIRPS before trusting low years):

| year | total_mm | day_cov |
|---|---|---|
| 2021 | - | 0.00 |
| 2022 | - | 0.00 |
| 2023 | - | 0.00 |
| 2024 | - | 0.00 |
| 2025 | - | 0.00 |

UTC hours carrying accumulation reports (the station's convention):

| accum | 5 |
|---|---|
| p6 | 0 |
| p12 | 0 |
| p24 | 1 |

### NII0000DNAA: barometer elevation


### NII0000DNAA vs DNAA METAR

- no coincident synop/METAR hours

## GHCNh NIM00065125

Location history (a change mid-record means the station moved):

| LATITUDE | LONGITUDE | ELEVATION | min | max | count |
|---|---|---|---|---|---|
| 9.25 | 7.0 | 344.0 | 2021-01-01 00:00:00 | 2026-10-04 06:00:00 | 14790 |

Temperature report types:

| temperature_Report_Type | rows |
|---|---|
| FM12 | 14741 |
| (blank) | 49 |

Temperature QC codes (non-good codes are dropped):

| temperature_Quality_Code | rows |
|---|---|
| 1 | 14589 |
| 2 | 113 |
| (blank) | 88 |

### NIM00065125: temperature and dewpoint

- training months with synoptic coverage >= 80%: 86% (need 75%)
- test-season days with derivable Tmax/Tmin: 86% (need 85%)
- longest unusable run in test season: 6 days (max 21)
- last valid observation: 2026-10-04 06:00:00
- verdict: PASS

Monthly synoptic-slot coverage, %:

| year | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2021 | 94 | 86 | 92 | 81 | 91 | 74 | 94 | 90 | 88 | 94 | 91 | 66 |
| 2022 | 78 | 88 | 93 | 90 | 89 | 76 | 75 | 90 | 94 | 94 | 93 | 88 |
| 2023 | 96 | 95 | 95 | 97 | 94 | 94 | 96 | 94 | 82 | 90 | 90 | 85 |
| 2024 | 82 | 88 | 94 | 93 | 88 | 93 | 93 | 96 | 93 | 92 | 82 | 75 |
| 2025 | 75 | 86 | 85 | 87 | 92 | 81 | 84 | 89 | 75 | 92 | - | - |

Share of days with an observation at each UTC hour, %:

| UTC hour | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 | 19 | 20 | 21 | 22 | 23 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train | 86 | 4 | 4 | 88 | 4 | 4 | 89 | 3 | 4 | 87 | 4 | 4 | 90 | 4 | 4 | 89 | 4 | 4 | 89 | 5 | 5 | 90 | 5 | 4 |
| test | 83 | 0 | 2 | 85 | 3 | 1 | 87 | 3 | 3 | 83 | 2 | 3 | 85 | 3 | 1 | 87 | 4 | 1 | 90 | 4 | 2 | 87 | 3 | 2 |

### NIM00065125: rain

- training wet-season days with a 24 h total: 11% (need 70%)
- test wet-season days with a 24 h total: 11% (need 80%)
- share of derivable days that are explicit zeros: 7%
- verdict: FAIL

Annual totals (compare against CHIRPS before trusting low years):

| year | total_mm | day_cov |
|---|---|---|
| 2021 | 245.00 | 0.05 |
| 2022 | 364.80 | 0.11 |
| 2023 | 292.70 | 0.07 |
| 2024 | 134.20 | 0.05 |
| 2025 | 141.40 | 0.08 |

UTC hours carrying accumulation reports (the station's convention):

| accum | 0 | 1 | 3 | 5 | 6 | 9 | 12 | 15 | 17 | 18 | 21 | 23 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| p6 | 106 | 0 | 0 | 0 | 61 | 1 | 140 | 1 | 1 | 174 | 0 | 1 |
| p12 | 172 | 1 | 0 | 0 | 128 | 1 | 4 | 1 | 0 | 130 | 1 | 0 |
| p24 | 5 | 0 | 1 | 1 | 127 | 3 | 2 | 0 | 0 | 2 | 0 | 0 |

### NIM00065125: barometer elevation


### NIM00065125 vs DNAA METAR

- coincident hours: 11761; bias -0.08 C; MAE 0.27 C; integer match 90%
- reading: same instrument

## IEM DNAA METAR

Reported location:

| lat | lon | elevation |
|---|---|---|
| 9.0068 | 7.2632 | 344.00 |

### DNAA: temperature and dewpoint

- training months with synoptic coverage >= 80%: 47% (need 75%)
- test-season days with derivable Tmax/Tmin: 85% (need 85%)
- longest unusable run in test season: 6 days (max 21)
- last valid observation: 2026-11-18 06:00:00
- verdict: FAIL

Monthly synoptic-slot coverage, %:

| year | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2021 | 62 | 69 | 65 | 64 | 69 | 55 | 80 | 73 | 73 | 66 | 58 | 60 |
| 2022 | 60 | 57 | 61 | 70 | 57 | 65 | 40 | 82 | 76 | 85 | 89 | 94 |
| 2023 | 88 | 80 | 81 | 82 | 87 | 86 | 87 | 84 | 60 | 76 | 78 | 73 |
| 2024 | 80 | 77 | 91 | 83 | 85 | 81 | 94 | 91 | 85 | 88 | 90 | 79 |
| 2025 | 82 | 71 | 85 | 84 | 83 | 79 | 79 | 91 | 82 | 86 | - | - |

Share of days with an observation at each UTC hour, %:

| UTC hour | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 | 19 | 20 | 21 | 22 | 23 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train | 69 | 78 | 77 | 69 | 83 | 82 | 77 | 84 | 87 | 80 | 84 | 85 | 77 | 86 | 85 | 78 | 85 | 83 | 78 | 87 | 85 | 78 | 84 | 80 |
| test | 85 | 82 | 85 | 83 | 85 | 82 | 85 | 86 | 82 | 81 | 78 | 76 | 81 | 79 | 73 | 83 | 85 | 84 | 85 | 85 | 85 | 85 | 85 | 83 |

## Gate

PARTIAL. Temperature truth: NIM00065125. Rain is verified against CHIRPS v3 only; rain claims in the demo are skill against satellite estimates, not gauges.

Change these keys in gnostiq.toml. Each already exists in its section:

```toml
[site]
ghcnh = "NIM00065125"

[truth]
temp = "ghcnh"
rain = "chirps"
```
