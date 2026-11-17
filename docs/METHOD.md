# Method note

## What this is

A statistical correction layer on top of a global weather model, for one site: Jos, Nigeria (WMO 65134, about 1295 m). It takes the model's forecast for the grid cell over Jos and produces calibrated probabilistic forecasts of 2 m temperature, 2 m dewpoint and 24 h rainfall for lead days 1 to 7. It does not run or train a global model, and it does not solve the equations of motion. The accurate name is physics-constrained post-processing.

## Inputs

- Forecasts: ECMWF IFS 0.25 degree by default, read through Open-Meteo. Training uses the Previous Runs archive, which stores for each valid hour the value forecast 24 x N hours earlier, N = 1..7, from January 2024.
- Temperature and dewpoint truth: station reports from NOAA GHCNh and airport METARs from the Iowa Environmental Mesonet, after quality control.
- Rain truth: the station gauge where the record allows it, otherwise CHIRPS v3 daily averaged over the 3 x 3 pixels (about 15 km) around the station.

## Where the physics enters

1. Terrain prior. The model grid cell over Jos sits at 1182 m; the station is listed at 1295 m. The network's starting point is the model temperature moved to station height along a lapse rate. With zero-initialised output weights the untrained network returns this prior exactly, so training only learns what the prior gets wrong. The code takes the lapse rate from the model's own 850 to 700 hPa layer when those fields exist; the lead-time archive used for training does not carry them, so in practice the standard 6.5 K/km applies.
2. Dewpoint cannot exceed temperature. The network predicts a dewpoint depression through a softplus link, so the constraint holds by construction for every input and every weight setting.
3. Rain is non-negative with a point mass at dry. A hurdle at the wet threshold (default 1 mm) with a gamma distribution for the excess.
4. Rain amount is tied to moisture supply. The network predicts a dimensionless efficiency; the conditional mean amount is efficiency times precipitable water. Efficiency above a cap (default 2) is penalised. The cap is soft and above one because a day of convergence can rain out more than the instantaneous column holds. The archive has no column water vapour for ECMWF, so precipitable water is estimated from the forecast surface dewpoint (Reitan 1963). That is a weaker constraint than the model's own column value.
5. Physically meaningful predictors: solar zenith angle, forecast shortwave radiation and cloud cover, and the north-easterly wind component that marks Harmattan flow. CAPE and mid-level humidity would belong here; the archive does not supply them for ECMWF.

## What it is compared against

All on identical cases from a test window the model never saw:

- climatology (harmonic fit for temperature, day-of-year window for rain)
- persistence
- the raw model, and the raw model after the terrain correction alone
- EMOS: non-homogeneous Gaussian regression for temperature and dewpoint, logistic plus gamma regression for rain, fitted per lead day

EMOS is the comparison that matters. Beating a raw model that sits at the wrong height shows little; a method that cannot beat EMOS has not earned its complexity.

## Scores

CRPS for all three variables, Brier score and equitable threat score at the wet and heavy thresholds, bias, mean absolute error, and coverage of the 80% interval. Skill scores carry 95% intervals from resampling whole days, because errors within a day are dependent. An interval that includes zero is reported as no demonstrated skill.

## Limits a reader should know

- One site. Nothing here shows the method transfers to other terrain or climate zones.
- At most about 27 months of training pairs and one test wet season. Confidence intervals are correspondingly wide for rain.
- ECMWF changed the IFS cycle on 12 May 2026, inside the default test window. Training data comes from the earlier cycle. This is what operational use looks like, but it means the test mixes two model versions.
- Where rain truth is CHIRPS, the scores measure agreement with a satellite-gauge blend whose day-to-day timing comes from IMERG ("sat") or ERA5 ("rnl"), not with a gauge at the station.
- Archived day-N forecasts have leads between 24 x N hours and one model cycle more. Live forecast steps are assigned the next lead day up, so live uncertainty is slightly overstated rather than understated.
- Temperature truth may mix synoptic reports (0.1 degC) and METARs (whole degrees), possibly from different instruments. The gate report shows whether they agree.
