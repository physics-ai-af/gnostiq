from dataclasses import replace

import numpy as np
import pandas as pd
import pytest
from conftest import write_cfg

from gnostiq import cfg
from gnostiq.ingest import station
from gnostiq.io import Missing


def obs(rows):
    o = pd.DataFrame(rows, columns=["slot", "p6", "p12", "p24"]).set_index("slot")
    o.index = pd.to_datetime(o.index)
    return o


def test_rain_day_runs_06_to_06_labelled_by_start():
    o = obs([("2025-07-02 06:00", np.nan, np.nan, 12.0)])
    r = station.rain_days(o, "2025-06-30", "2025-07-03")
    assert r[pd.Timestamp("2025-07-01")] == 12.0 and r.notna().sum() == 1


def test_rain_day_falls_back_to_shorter_accumulations():
    o = obs([("2025-07-01 18:00", np.nan, 3.0, np.nan), ("2025-07-02 06:00", np.nan, 4.0, np.nan),
             ("2025-07-03 12:00", 1.0, np.nan, np.nan), ("2025-07-03 18:00", 1.0, np.nan, np.nan),
             ("2025-07-04 00:00", 1.0, np.nan, np.nan), ("2025-07-04 06:00", 1.0, np.nan, np.nan)])  # fmt: skip
    r = station.rain_days(o, "2025-07-01", "2025-07-03")
    assert r[pd.Timestamp("2025-07-01")] == 7.0 and r[pd.Timestamp("2025-07-03")] == 4.0
    assert np.isnan(r[pd.Timestamp("2025-07-02")])


def test_rain_day_needs_every_piece():
    o = obs([("2025-07-03 12:00", 1.0, np.nan, np.nan), ("2025-07-03 18:00", 1.0, np.nan, np.nan),
             ("2025-07-04 06:00", 1.0, np.nan, np.nan)])  # fmt: skip
    assert station.rain_days(o, "2025-07-03", "2025-07-03").isna().all()


def test_slotted_snaps_near_the_hour_and_drops_half_hour_reports():
    ts = pd.to_datetime(["2025-07-01 11:55", "2025-07-01 12:30", "2025-07-01 13:05", "2025-07-01 13:08"])
    s = station.slotted(pd.DataFrame({"ts": ts, "t": [1.0, 2.0, 3.0, 4.0]}))
    assert s.index.tolist() == [pd.Timestamp("2025-07-01 12:00"), pd.Timestamp("2025-07-01 13:00")]
    assert s.t.tolist() == [1.0, 3.0]


def ghcnh_rows(**cols):
    base = {"ts": pd.to_datetime(["2025-07-01 00:00", "2025-07-01 03:00", "2025-07-01 06:00"])}
    return pd.DataFrame({**base, **cols})


def test_tidy_drops_values_that_failed_noaa_checks():
    df = ghcnh_rows(temperature=["20.1", "21.0", "22.5"], temperature_Quality_Code=["5", "3", ""],
                    temperature_Report_Type=["FM-12", "FM-12", "FM-15"])  # fmt: skip
    o = station.tidy_ghcnh(df)
    assert o.t.tolist()[0] == 20.1 and np.isnan(o.t.iloc[1]) and o.t.iloc[2] == 22.5
    assert o.rtype.tolist() == ["FM-12", "FM-12", "FM-15"]


def test_tidy_reads_trace_rain_as_zero_but_leaves_pressure_alone():
    df = ghcnh_rows(precipitation_6_hour=["", "1.2", ""], precipitation_6_hour_Measurement_Code=["T", "", ""],
                    station_level_pressure=["", "871.0", "870.5"],
                    station_level_pressure_Measurement_Code=["T", "", ""])  # fmt: skip
    o = station.tidy_ghcnh(df)
    assert o.p6.iloc[0] == 0.0 and o.p6.iloc[1] == 1.2 and np.isnan(o.p6.iloc[2])
    assert np.isnan(o.ps.iloc[0]) and o.ps.iloc[1] == 871.0


def test_tidy_fills_absent_columns_with_nan():
    o = station.tidy_ghcnh(ghcnh_rows(temperature=["20", "21", "22"]))
    assert o.td.isna().all() and o.p24.isna().all() and set(station.OBS) <= set(o.columns)


@pytest.mark.parametrize("stamp", ["single", "split"])
def test_read_ghcnh_accepts_both_timestamp_layouts(tmp_path, stamp):
    if stamp == "single":
        head, rows = "DATE|temperature", ["2020-12-31T21:00:00|18.0", "2021-01-01T00:00:00|19.0"]
    else:
        head, rows = "Year|Month|Day|Hour|Minute|temperature", ["2020|12|31|21|0|18.0", "2021|1|1|0|0|19.0"]
    path = tmp_path / "g.psv"
    path.write_text("\n".join([head, *rows]) + "\n")
    df = station.read_ghcnh(path, "2021-01-01")
    assert df.ts.tolist() == [pd.Timestamp("2021-01-01 00:00")] and df.temperature.tolist() == ["19.0"]


def test_read_iem_converts_units_and_missing_markers(tmp_path):
    path = tmp_path / "iem.csv"
    path.write_text(
        "station,valid,lon,lat,elevation,tmpf,dwpf,alti,mslp,sknt\n"
        "DNJO,2025-07-01 12:00,8.87,9.64,1290.0,77.00,59.00,30.00,M,10.0\n"
        "DNJO,2025-07-01 13:00,8.87,9.64,1290.0,M,M,M,M,M\n"
    )
    o, meta = station.read_iem([path])
    row = o.loc[pd.Timestamp("2025-07-01 12:00")]
    assert row.t == pytest.approx(25.0) and row.td == pytest.approx(15.0)
    assert row.qnh == pytest.approx(1015.9, abs=0.1) and row.wspd == pytest.approx(5.14, abs=0.01)
    assert np.isnan(row.slp) and o.loc[pd.Timestamp("2025-07-01 13:00")].isna().all()
    assert meta.elevation.tolist() == ["1290.0"]


@pytest.mark.parametrize(
    "line",
    [
        "NIM00065134   9.8667    8.9000 1295.0    JOS                                    65134",
        "NIM00065134,9.8667,8.9000,1295.0,,JOS,,,65134",
    ],
)
def test_station_list_parse_tolerates_layout(tmp_path, line):
    c = cfg.load(write_cfg(tmp_path))
    d = c.paths.raw / "station"
    d.mkdir(parents=True)
    (d / "ghcnh-station-list.txt").write_text(
        "USW00003812  35.4317  -82.5378  645.6 NC ASHEVILLE AP 72315\n" + line + "\n"
    )
    cand = station.candidates(c)
    assert cand.id.tolist() == ["NIM00065134"] and bool(cand.wmo.iloc[0])
    assert station.resolve_id(c) == "NIM00065134"


def test_ambiguous_station_needs_an_explicit_id(tmp_path):
    c = cfg.load(write_cfg(tmp_path))
    d = c.paths.raw / "station"
    d.mkdir(parents=True)
    (d / "ghcnh-station-list.txt").write_text(
        "AAA00000001   9.80   8.90 1290.0 JOS A\nAAA00000002   9.65   8.87 1285.0 JOS B\n"
    )
    with pytest.raises(Missing, match="2 GHCNh candidates"):
        station.resolve_id(c)
    assert station.resolve_id(replace(c, site=replace(c.site, ghcnh="AAA00000002"))) == "AAA00000002"


def test_build_merges_sources_with_ghcnh_first(station_raw):
    c = station_raw
    o = station.build(c)
    assert set(o.src) == {"ghcnh", "iem"} and o.index.is_monotonic_increasing and o.index.is_unique
    # the station's 0.1 degC value wins over the METAR
    both = o[(o.src == "ghcnh") & (o.index.hour == 12)]
    assert (both.t.round() != both.t).any()
    saved = pd.read_parquet(c.paths.interim / "station.parquet")
    assert list(saved.columns) == ["valid", *station.OBS, "src"] and len(saved) == len(o)
    assert (c.paths.interim / "station_rain.parquet").exists()


@pytest.mark.parametrize("mode, hours", [("ghcnh", {0, 3, 6, 9, 12, 15, 18, 21}), ("iem", set(range(7, 18)))])
def test_build_single_source(station_raw, mode, hours):
    o = station.build(replace(station_raw, truth=replace(station_raw.truth, temp=mode)))
    assert set(o.src) == {mode} and set(o.index.hour) == hours


def test_build_without_files_says_what_to_run(tmp_path):
    c = cfg.load(write_cfg(tmp_path))
    with pytest.raises(FileNotFoundError, match="gnostiq pull"):
        station.build(c)
