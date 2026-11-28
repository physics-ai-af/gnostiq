# Learning curve: abuja

Training pairs are whole weeks drawn at random from 2024-02-29 to 2025-03-31, so every size spans the seasons, and each size contains the smaller ones. EMOS and gnostiq are refit at every size; climatology always uses the full station record, because it needs no archived forecasts. Every system is scored on the same cases from 2025-04-01 to 2025-10-31.

Skill is 1 - CRPS/reference; brackets are 95% intervals from resampling whole days. emos_multi is EMOS given the same extra models as gnostiq.

## t2m

| training | weeks | pairs | CRPS clim | CRPS emos | CRPS emos_multi | CRPS gnostiq | vs emos | vs emos_multi | vs clim |
|---|---|---|---|---|---|---|---|---|---|
| 1 mo | 4 | 1,603 | 0.947 | 0.918 | 0.901 | 0.941 | -0.025 [-0.058, +0.005] | -0.045 [-0.081, -0.012] | +0.006 [-0.044, +0.056] |
| 2 mo | 9 | 3,486 | 0.947 | 0.909 | 0.842 | 0.889 | +0.021 [+0.003, +0.038] | -0.056 [-0.085, -0.030] | +0.061 [+0.012, +0.103] |
| 3 mo | 13 | 5,040 | 0.947 | 0.941 | 0.851 | 0.874 | +0.071 [+0.052, +0.090] | -0.027 [-0.049, -0.007] | +0.076 [+0.034, +0.117] |
| 6 mo | 26 | 10,228 | 0.947 | 0.922 | 0.842 | 0.814 | +0.118 [+0.094, +0.142] | +0.034 [+0.009, +0.059] | +0.141 [+0.107, +0.174] |
| all | 58 | 21,733 | 0.947 | 0.951 | 0.837 | 0.799 | +0.160 [+0.136, +0.186] | +0.046 [+0.022, +0.069] | +0.156 [+0.121, +0.194] |

## td2m

| training | weeks | pairs | CRPS clim | CRPS emos | CRPS emos_multi | CRPS gnostiq | vs emos | vs emos_multi | vs clim |
|---|---|---|---|---|---|---|---|---|---|
| 1 mo | 4 | 1,603 | 0.777 | 0.714 | 0.688 | 0.688 | +0.036 [-0.005, +0.077] | -0.000 [-0.041, +0.039] | +0.114 [+0.064, +0.159] |
| 2 mo | 9 | 3,486 | 0.777 | 0.704 | 0.657 | 0.663 | +0.058 [+0.030, +0.086] | -0.009 [-0.037, +0.017] | +0.147 [+0.099, +0.194] |
| 3 mo | 13 | 5,040 | 0.777 | 0.757 | 0.683 | 0.726 | +0.041 [+0.010, +0.072] | -0.064 [-0.095, -0.035] | +0.066 [+0.010, +0.115] |
| 6 mo | 26 | 10,228 | 0.777 | 0.701 | 0.684 | 0.729 | -0.040 [-0.068, -0.012] | -0.065 [-0.086, -0.045] | +0.063 [+0.011, +0.110] |
| all | 58 | 21,733 | 0.777 | 0.742 | 0.704 | 0.699 | +0.057 [+0.025, +0.087] | +0.006 [-0.017, +0.031] | +0.100 [+0.055, +0.144] |
