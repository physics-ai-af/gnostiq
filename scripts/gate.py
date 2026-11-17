#!/usr/bin/env python3
"""Station data gate. Writes data/reports/gate.md."""

import sys

import numpy as np
import pandas as pd

from gnostiq import cfg
from gnostiq.ingest import station
from gnostiq.io import Missing

C = cfg.get()
START, TRAIN_END = pd.Timestamp(C.window.start), pd.Timestamp(C.window.train_end)
TEST0, TEST1 = pd.Timestamp(C.window.test_start), pd.Timestamp(C.window.test_end)
WET = list(C.window.wet)
SYN = list(range(0, 24, 3))

# working thresholds
MIN_SLOT_COV = 0.80  # monthly share of synoptic slots
MIN_GOOD_MONTHS = 0.75  # training months meeting it
MIN_TEST_DAYS = 0.85  # test days with Tmax and Tmin
MAX_TEST_GAP = 21  # days
MIN_P_TRAIN = 0.70  # wet-season days with a 24 h total
MIN_P_TEST = 0.80


def longest_run(ok):
    run = best = 0
    for x in ok:
        run = 0 if x else run + 1
        best = max(best, run)
    return best


def temp_metrics(o):
    v = o.t.notna() & o.td.notna()
    idx = pd.date_range(START, TEST1 + pd.Timedelta(hours=23), freq="h")
    h = v.reindex(idx, fill_value=False)
    hr, day = idx.hour, idx.normalize()

    syn_mask = np.isin(hr, SYN)
    syn = pd.Series(h.to_numpy()[syn_mask], index=idx[syn_mask])
    monthly = syn.groupby(syn.index.to_period("M")).mean()
    train = monthly[monthly.index <= TRAIN_END.to_period("M")]

    # Tmin needs a pre-dawn obs, Tmax an afternoon one
    n_syn = syn.groupby(syn.index.normalize()).sum()
    lo = (hr >= 3) & (hr <= 7)
    hi = (hr >= 12) & (hr <= 16)
    tmin = pd.Series(h.to_numpy()[lo], index=day[lo]).groupby(level=0).any()
    tmax = pd.Series(h.to_numpy()[hi], index=day[hi]).groupby(level=0).any()
    days_ok = (n_syn >= 6) & tmin & tmax
    test = days_ok[TEST0:TEST1]

    return {
        "good_months": (train >= MIN_SLOT_COV).mean() if len(train) else np.nan,
        "test_days": test.mean() if len(test) else np.nan,
        "test_gap": longest_run(test) if len(test) else np.nan,
        "last_obs": v[v].index.max() if v.any() else None,
        "monthly": monthly,
        "profile_train": h[h.index < TEST0].groupby(h.index[h.index < TEST0].hour).mean(),
        "profile_test": h[h.index >= TEST0].groupby(h.index[h.index >= TEST0].hour).mean(),
    }


def precip_metrics(o):
    p = station.rain_days(o, START, TEST1)
    ok = p.notna()
    wet = ok[ok.index.month.isin(WET)]
    year = pd.Index(p.index.year, name="year")
    hours = pd.DataFrame({k: o[k].dropna().index.hour.value_counts() for k in ("p6", "p12", "p24")})
    hours = hours.fillna(0).astype(int).sort_index().T
    hours.index.name = "accum"
    return {
        "p_train": wet[:TRAIN_END].mean(),
        "p_test": wet[TEST0:TEST1].mean(),
        "zero_share": (p[ok] == 0).mean() if ok.any() else np.nan,
        "annual": pd.DataFrame({"total_mm": p.groupby(year).sum(min_count=1), "day_cov": ok.groupby(year).mean()}),
        "report_hours": hours,
    }


def elevation(o):
    out = {}
    ok = o.ps.between(800, 950)
    q = o.ps[ok] / o.qnh[o.qnh.between(980, 1050)]
    out["isa_from_qnh"] = (44330.77 * (1 - q.dropna() ** 0.190263)).clip(0, 3000)
    tm = o.t + 273.15 + 4.2  # mean column temp
    z = 29.27 * tm * np.log(o.slp[o.slp.between(980, 1050)] / o.ps[ok])
    out["hypsometric_from_slp"] = z.dropna().clip(0, 3000)
    return out


def colocate(g, m):
    synop = g[~g.rtype.str.contains("15|16|SAO|METAR", case=False, regex=True)]
    j = synop[["t"]].join(m[["t"]].rename(columns={"t": "t_m"}), how="inner").dropna()
    if j.empty:
        return None
    d = j.t - j.t_m
    return {"n": len(j), "bias": d.mean(), "mae": d.abs().mean(), "exact": (j.t.round() == j.t_m.round()).mean()}


def t_pass(m):
    return m["good_months"] >= MIN_GOOD_MONTHS and m["test_days"] >= MIN_TEST_DAYS and m["test_gap"] <= MAX_TEST_GAP


def p_pass(m):
    return m["p_train"] >= MIN_P_TRAIN and m["p_test"] >= MIN_P_TEST


def fmt(x, pct=False):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "-"
    if pct:
        return f"{x * 100:.0f}"
    if isinstance(x, float | np.floating):
        return f"{x:.2f}"
    return str(x)


def table(df, pct=False):
    cols = [str(c) for c in df.columns]
    out = ["| " + " | ".join([str(df.index.name or "")] + cols) + " |", "|" + "---|" * (len(cols) + 1)]
    for i, row in df.iterrows():
        out.append("| " + " | ".join([str(i)] + [fmt(x, pct) for x in row]) + " |")
    return out + [""]


def temp_section(name, m):
    mon = m["monthly"].to_frame("c")
    mon["y"], mon["m"] = mon.index.year, mon.index.month
    piv = mon.pivot(index="y", columns="m", values="c")
    piv.index.name = "year"
    prof = pd.DataFrame({"train": m["profile_train"], "test": m["profile_test"]}).T
    prof.index.name = "UTC hour"
    lines = [
        f"### {name}: temperature and dewpoint",
        "",
        f"- training months with synoptic coverage >= {MIN_SLOT_COV:.0%}: {fmt(m['good_months'], True)}%"
        f" (need {MIN_GOOD_MONTHS:.0%})",
        f"- test-season days with derivable Tmax/Tmin: {fmt(m['test_days'], True)}% (need {MIN_TEST_DAYS:.0%})",
        f"- longest unusable run in test season: {fmt(m['test_gap'])} days (max {MAX_TEST_GAP})",
        f"- last valid observation: {m['last_obs']}",
        f"- verdict: {'PASS' if t_pass(m) else 'FAIL'}",
        "",
        "Monthly synoptic-slot coverage, %:",
        "",
    ]
    lines += table(piv, pct=True) + ["Share of days with an observation at each UTC hour, %:", ""]
    return lines + table(prof, pct=True)


def main():
    C.paths.ensure()
    rep = [
        "# Station data gate",
        "",
        f"Window {START.date()} to {TEST1.date()}; training ends {TRAIN_END.date()}; "
        f"test season {TEST0.date()} to {TEST1.date()}.",
        "",
    ]

    if len(sys.argv) > 1:
        ids = sys.argv[1:]
    elif C.site.ghcnh:
        ids = [C.site.ghcnh]
    else:
        cand = station.candidates(C)
        rep += ["## GHCNh records near the site", ""] + table(cand.set_index("id"))
        ids = list(cand.id)
    if not ids:
        sys.exit(
            f"No GHCNh record for WMO {C.site.wmo} or inside {C.site.bbox}. Search the station list and pass the id."
        )

    try:
        iem, iem_meta = station.read_iem(station.iem_paths(C))
    except Missing as e:
        sys.exit(f"IEM has no data for {C.site.icao}: {e}")
    iem = iem.assign(ps=np.nan)
    t_src, p_src = None, None

    for sid in ids:
        raw = station.read_ghcnh(station.ghcnh_path(C, sid), START)
        o = station.tidy_ghcnh(raw)
        meta = raw.groupby(["Latitude", "Longitude", "Elevation"], dropna=False).ts.agg(["min", "max", "count"])
        qc = station.text(raw, "temperature_Quality_Code").replace("", "(blank)").value_counts().to_frame("rows")
        rtypes = station.text(raw, "temperature_Report_Type").replace("", "(blank)").value_counts().to_frame("rows")
        tm, pm = temp_metrics(o), precip_metrics(o)

        rep += [f"## GHCNh {sid}", "", "Location history (a change mid-record means the station moved):", ""]
        rep += table(meta.reset_index().set_index("Latitude"))
        rep += ["Temperature report types:", ""] + table(rtypes)
        rep += ["Temperature QC codes (non-good codes are dropped):", ""] + table(qc)
        rep += temp_section(sid, tm)

        rep += [
            f"### {sid}: rain",
            "",
            f"- training wet-season days with a 24 h total: {fmt(pm['p_train'], True)}% (need {MIN_P_TRAIN:.0%})",
            f"- test wet-season days with a 24 h total: {fmt(pm['p_test'], True)}% (need {MIN_P_TEST:.0%})",
            f"- share of derivable days that are explicit zeros: {fmt(pm['zero_share'], True)}%",
            f"- verdict: {'PASS' if p_pass(pm) else 'FAIL'}",
            "",
            "Annual totals (compare against CHIRPS before trusting low years):",
            "",
        ]
        rep += table(pm["annual"]) + ["UTC hours carrying accumulation reports (the station's convention):", ""]
        rep += table(pm["report_hours"])

        rep += [f"### {sid}: barometer elevation", ""]
        for k, z in elevation(o).items():
            if len(z):
                q1, q3 = z.quantile(0.25), z.quantile(0.75)
                rep.append(f"- {k}: median {z.median():.0f} m, IQR {q1:.0f} to {q3:.0f} m, n={len(z)}")
        rep.append("")

        co = colocate(o, iem)
        rep += [f"### {sid} vs {C.site.icao} METAR", ""]
        if co:
            same = co["exact"] >= 0.8 and abs(co["bias"]) < 0.3
            rep += [
                f"- coincident hours: {co['n']}; bias {co['bias']:+.2f} C; MAE {co['mae']:.2f} C; "
                f"integer match {co['exact']:.0%}",
                f"- reading: {'same instrument' if same else 'different site or sensor'}"
                f"{' (n < 200, inconclusive)' if co['n'] < 200 else ''}",
                "",
            ]
        else:
            rep += ["- no coincident synop/METAR hours", ""]

        if t_src is None and t_pass(tm):
            t_src = ("ghcnh", sid)
        if p_src is None and p_pass(pm):
            p_src = sid

    im = temp_metrics(iem)
    rep += [f"## IEM {C.site.icao} METAR", "", "Reported location:", ""]
    rep += table(iem_meta.set_index(iem_meta.columns[0])) + temp_section(C.site.icao, im)
    if t_src is None and t_pass(im):
        t_src = ("iem", C.site.icao)

    rep += ["## Gate", ""]
    if t_src and p_src:
        rep.append(f"PASS. Temperature truth: {t_src[1]}. Rain truth: station gauge, cross-checked against CHIRPS v3.")
        rep += ["", "Set in gnostiq.toml:", "", "```toml", f'site.ghcnh = "{p_src}"', f'truth.temp = "{t_src[0]}"']
        rep += ['truth.rain = "station"', "```"]
    elif t_src:
        rep.append(
            f"PARTIAL. Temperature truth: {t_src[1]}. Rain is verified against CHIRPS v3 only; "
            "rain claims in the demo are skill against satellite estimates, not gauges."
        )
        rep += ["", "Set in gnostiq.toml:", "", "```toml", f'truth.temp = "{t_src[0]}"', 'truth.rain = "chirps"', "```"]
    else:
        rep.append(
            "FAIL. No source meets the temperature thresholds. Read the hour-of-day profiles above: a station "
            'that only reports by day can still verify daytime hours with truth.temp = "merged", but the claim '
            "narrows to those hours. Otherwise the NiMet record request or an own station is the blocker."
        )

    out = C.paths.reports / "gate.md"
    out.write_text("\n".join(rep) + "\n")
    print(rep[rep.index("## Gate") + 2])
    print(f"report: {out}")


if __name__ == "__main__":
    main()
