"""Thermodynamics, terrain prior, feature builders."""

import numpy as np
import pandas as pd

RD_G = 29.2717  # Rd/g, m/K
G_STD = 0.0065  # K/m
TD_LAPSE = 0.0018  # K/m, well-mixed layer

HOURLY_FEATS = [
    "t_prior", "td_prior", "f_t2m", "f_td2m", "f_msl", "f_cloud", "f_u", "f_v", "ne", "f_cape", "f_tcwv", "f_sw",
    "f_t850", "f_t700", "f_rh700", "f_wspd850", "f_tp", "tp6", "dt3", "gamma", "cosz", "hod_s", "hod_c", "doy_s",
    "doy_c", "lead_day",
]  # fmt: skip
DAILY_FEATS = [
    "f_tp24", "f_tp24_sqrt", "f_tpmax", "tcwv_max", "tcwv_mean", "cape_max", "cape_mean", "cloud_mean", "dep_mean",
    "t_mean", "t_max", "msl_mean", "wspd_mean", "ne_mean", "rh700_mean", "sw_mean", "doy_s", "doy_c", "lead_day",
]  # fmt: skip
NWP_COLS = [
    "f_t2m", "f_td2m", "f_tp", "f_msl", "f_sp", "f_cloud", "f_wspd", "f_wdir", "f_cape", "f_tcwv", "f_sw", "f_t850",
    "f_t700", "f_rh700", "f_wspd850", "f_wdir850",
]  # fmt: skip


def extra_feats(models):
    return [f"x_{m}_{v}" for m in models for v in ("dt2m", "dtd2m", "ok")]


def extra_deltas(df, var):
    return [k for k in df if k.startswith("x_") and k.endswith(f"_d{var}")]


def add_extras(df, extras, keys=("valid", "lead_day")):
    # other models as offsets from the base, so the net can learn when to trust which
    keys = list(keys)
    for m, e in extras.items():
        e = e[[*keys, "f_t2m", "f_td2m"]].drop_duplicates(keys).rename(columns={"f_t2m": "_t", "f_td2m": "_td"})
        df = df.merge(e, on=keys, how="left")
        df[f"x_{m}_dt2m"] = df._t - df.f_t2m
        df[f"x_{m}_dtd2m"] = df._td - df.f_td2m
        df[f"x_{m}_ok"] = df._t.notna().astype(float)
        df = df.drop(columns=["_t", "_td"])
    return df


def es(t):
    return 6.112 * np.exp(17.67 * t / (t + 243.5))


def rh(t, td):
    return 100.0 * es(td) / es(t)


def thickness(p_bot, p_top, t_mean):
    return RD_G * (t_mean + 273.15) * np.log(p_bot / p_top)


def lapse(t850, t700):
    g = (t850 - t700) / thickness(850.0, 700.0, (t850 + t700) / 2)
    return np.where(np.isfinite(g), np.clip(g, 0.003, 0.0098), G_STD)


def height(sp, msl, t2m):
    z = RD_G * (t2m + 273.15) * np.log(msl / sp)
    for _ in range(2):
        z = RD_G * (t2m + 273.15 + G_STD * z / 2) * np.log(msl / sp)
    return z


def pw_from_td(td, sp):
    return 10.0 * np.exp(0.1102 + 0.0614 * td) * sp / 1013.25


def cos_zenith(time, lat, lon):
    time = pd.DatetimeIndex(time)
    hr = (time.hour + time.minute / 60).to_numpy(dtype=float)
    g = 2 * np.pi / 365 * (time.day_of_year.to_numpy() - 1 + (hr - 12) / 24)
    decl = (
        0.006918
        - 0.399912 * np.cos(g)
        + 0.070257 * np.sin(g)
        - 0.006758 * np.cos(2 * g)
        + 0.000907 * np.sin(2 * g)
        - 0.002697 * np.cos(3 * g)
        + 0.00148 * np.sin(3 * g)
    )
    eot = 229.18 * (
        0.000075 + 0.001868 * np.cos(g) - 0.032077 * np.sin(g) - 0.014615 * np.cos(2 * g) - 0.040849 * np.sin(2 * g)
    )
    ha = np.radians((hr * 60 + eot + 4 * lon) / 4 - 180)
    la = np.radians(lat)
    return np.sin(la) * np.sin(decl) + np.cos(la) * np.cos(decl) * np.cos(ha)


def hourly_features(df, site, z_model):
    df = df.sort_values(["lead_day", "valid"]).reset_index(drop=True)
    for c in NWP_COLS:
        if c not in df:
            df[c] = np.nan

    dz = z_model - site.elev
    gam = lapse(df.f_t850.to_numpy(float), df.f_t700.to_numpy(float))
    df["gamma"] = gam * 1000
    df["t_prior"] = df.f_t2m + gam * dz
    df["td_prior"] = np.minimum(df.f_td2m + TD_LAPSE * dz, df.t_prior)
    df["dep_prior"] = df.t_prior - df.td_prior
    df["sp_prior"] = df.f_sp * np.exp(dz / (RD_G * (df.t_prior + 273.15)))

    d = np.radians(df.f_wdir)
    df["f_u"] = -df.f_wspd * np.sin(d)
    df["f_v"] = -df.f_wspd * np.cos(d)
    # positive in Harmattan flow
    df["ne"] = -(df.f_u + df.f_v) / np.sqrt(2)

    by = df.groupby("lead_day", sort=False)
    df["tp6"] = by.f_tp.transform(lambda s: s.rolling(6, min_periods=3).sum())
    df["dt3"] = by.f_t2m.diff(3)

    t = pd.DatetimeIndex(df.valid)
    df["cosz"] = cos_zenith(t, site.lat, site.lon)
    solar = 2 * np.pi * ((t.hour + t.minute / 60 + site.lon / 15) % 24) / 24
    doy = 2 * np.pi * t.day_of_year / 365.25
    df["hod_s"], df["hod_c"] = np.sin(solar), np.cos(solar)
    df["doy_s"], df["doy_c"] = np.sin(doy), np.cos(doy)
    return df


def rain_sum(h, h0, keys=("lead_day",)):
    # precip at t covers the hour ending at t
    keys = list(keys)
    day = (h.valid - pd.Timedelta(hours=h0 + 1)).dt.floor("D").rename("day")
    g = h.groupby([*[h[k] for k in keys], day]).f_tp.agg(["sum", "count"])
    return g.loc[g["count"] == 24, "sum"].rename("f_tp24").reset_index()


def daily_features(h, h0, keys=("lead_day",)):
    # open-meteo precip at t covers the hour ending at t
    keys = list(keys)
    h = h.copy()
    off = pd.Timedelta(hours=h0)
    h["day"] = (h.valid - off).dt.floor("D")
    h["day_tp"] = (h.valid - off - pd.Timedelta(hours=1)).dt.floor("D")
    h["dep"] = h.f_t2m - h.f_td2m

    tp = h.groupby([*keys, "day_tp"]).agg(f_tp24=("f_tp", "sum"), f_tpmax=("f_tp", "max"), n_tp=("f_tp", "count"))
    tp.index = tp.index.set_names([*keys, "day"])
    inst = h.groupby([*keys, "day"]).agg(
        n=("f_t2m", "count"),
        tcwv_max=("f_tcwv", "max"),
        tcwv_mean=("f_tcwv", "mean"),
        cape_max=("f_cape", "max"),
        cape_mean=("f_cape", "mean"),
        cloud_mean=("f_cloud", "mean"),
        dep_mean=("dep", "mean"),
        t_mean=("f_t2m", "mean"),
        t_max=("f_t2m", "max"),
        td_max=("f_td2m", "max"),
        sp_mean=("f_sp", "mean"),
        msl_mean=("f_msl", "mean"),
        wspd_mean=("f_wspd", "mean"),
        ne_mean=("ne", "mean"),
        rh700_mean=("f_rh700", "mean"),
        sw_mean=("f_sw", "mean"),
    )
    d = tp.join(inst, how="inner")
    d = d[(d.n_tp == 24) & (d.n == 24)].drop(columns=["n_tp", "n"]).reset_index()

    d["f_tp24_sqrt"] = np.sqrt(d.f_tp24.clip(lower=0))
    # model tcwv if present, else Reitan from dewpoint
    d["pw"] = d.tcwv_max.where(d.tcwv_max.notna(), pw_from_td(d.td_max, d.sp_mean.fillna(870.0))).clip(lower=5.0)
    doy = 2 * np.pi * d.day.dt.day_of_year / 365.25
    d["doy_s"], d["doy_c"] = np.sin(doy), np.cos(doy)
    return d
