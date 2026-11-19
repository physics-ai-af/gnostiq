"""Run configuration from gnostiq.toml."""

import functools
import os
import re
import tomllib
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

FILENAME = "gnostiq.toml"


@dataclass(frozen=True)
class Var:
    unit: str
    lo: float
    hi: float


# gross limits; qc applies the tighter ones
VARS = {
    "t": Var("degC", -10, 50),
    "td": Var("degC", -40, 35),
    "tp24": Var("mm", 0, 600),
    "wspd": Var("m/s", 0, 60),
    "slp": Var("hPa", 950, 1060),
    "ps": Var("hPa", 750, 1000),
    "qnh": Var("hPa", 950, 1060),
}


@dataclass(frozen=True)
class Site:
    name: str
    wmo: str
    icao: str
    ghcnh: str
    lat: float
    lon: float
    elev: float
    tz: str
    bbox: tuple[float, float, float, float]


@dataclass(frozen=True)
class Window:
    start: date
    train_end: date
    test_start: date
    test_end: date
    wet: tuple[int, ...]


@dataclass(frozen=True)
class Truth:
    temp: str
    rain: str
    chirps_flavor: str

    @property
    def rain_h0(self):
        # synop rain days run 06-06 UTC, CHIRPS 00-00
        return 6 if self.rain == "station" else 0


@dataclass(frozen=True)
class Nwp:
    base: str
    extra: tuple[str, ...]
    start: date
    chunk_days: int
    compare: tuple[str, ...] = ()  # scored and drawn, never fed to the networks

    @property
    def others(self):
        return (*self.extra, *self.compare)


@dataclass(frozen=True)
class Model:
    seeds: int
    hidden: int
    max_epochs: int
    patience: int
    eff_max: float


@dataclass(frozen=True)
class Paths:
    data: Path
    home: Path | None = None  # data directory of the site whose networks these are

    @property
    def raw(self):
        return self.data / "raw"

    @property
    def interim(self):
        return self.data / "interim"

    @property
    def processed(self):
        return self.data / "processed"

    @property
    def models(self):
        return (self.home or self.data) / "models"

    @property
    def trained(self):
        # the training pairs behind those networks
        return (self.home or self.data) / "processed"

    @property
    def reports(self):
        return self.data / "reports"

    @property
    def archive(self):
        return self.data / "archive"

    def ensure(self):
        for p in (self.raw, self.interim, self.processed, self.models, self.reports, self.archive):
            p.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class Cfg:
    site: Site
    window: Window
    truth: Truth
    nwp: Nwp
    lead_days: tuple[int, ...]
    wet_mm: float
    heavy_mm: float
    model: Model
    paths: Paths
    source: Path
    donor: str = ""  # site whose networks this one runs; empty means its own


def find():
    env = os.environ.get("GNOSTIQ_CFG")
    if env:
        return Path(env)
    here = Path.cwd().resolve()
    for d in (here, *here.parents):
        if (d / FILENAME).is_file():
            return d / FILENAME
    raise FileNotFoundError(f"{FILENAME} not found from {here} upward; set GNOSTIQ_CFG")


def read(path):
    with path.open("rb") as f:
        return tomllib.load(f)


def load(path=None, site=None):
    path = Path(path or find()).resolve()
    raw = read(path)
    tables = raw.get("sites") or {}
    if not tables and "site" in raw:
        raise ValueError(f"{path}: [site] and [paths] are now one [sites.<name>] table per site, with data in it")
    if not tables:
        raise ValueError(f"{path}: no [sites.<name>] table")
    name = site or os.environ.get("GNOSTIQ_SITE") or next(iter(tables))
    if name not in tables:
        raise ValueError(f"{path}: no site {name!r}; it has {', '.join(tables)}")
    t = tables[name]

    def need(section, key):
        try:
            return raw[section][key]
        except KeyError:
            raise ValueError(f"{path}: missing {section}.{key}") from None

    def own(key):
        try:
            return t[key]
        except KeyError:
            raise ValueError(f"{path}: missing sites.{name}.{key}") from None

    donor = t.get("borrow", "")
    if donor:
        # the networks only hold where window, truth, inputs and leads match their training; shared settings ensure it
        if donor == name or donor not in tables:
            raise ValueError(f"{path}: sites.{name}.borrow must name another site: {donor!r}")
        if tables[donor].get("borrow"):
            raise ValueError(f"{path}: sites.{name} borrows from {donor}, which borrows too")
    data = {n: (path.parent / x.get("data", "")).resolve() for n, x in tables.items()}
    if list(data.values()).count(data[name]) > 1:
        raise ValueError(f"{path}: sites.{name}.data is shared with another site")

    site = Site(
        name=name,
        wmo=str(own("wmo")),
        icao=own("icao"),
        ghcnh=t.get("ghcnh", ""),
        lat=float(own("lat")),
        lon=float(own("lon")),
        elev=float(own("elev_m")),
        tz=own("tz"),
        bbox=tuple(float(x) for x in own("bbox")),
    )
    win = Window(
        start=need("window", "start"),
        train_end=need("window", "train_end"),
        test_start=need("window", "test_start"),
        test_end=need("window", "test_end"),
        wet=tuple(need("window", "wet_months")),
    )
    truth = Truth(
        temp=need("truth", "temp"),
        rain=need("truth", "rain"),
        chirps_flavor=need("truth", "chirps_flavor"),
    )
    nwp = Nwp(
        base=need("nwp", "base"),
        extra=tuple(need("nwp", "extra")),
        start=need("nwp", "start"),
        chunk_days=int(need("nwp", "chunk_days")),
        compare=tuple(raw["nwp"].get("compare", [])),
    )
    model = Model(
        seeds=int(need("model", "seeds")),
        hidden=int(need("model", "hidden")),
        max_epochs=int(need("model", "max_epochs")),
        patience=int(need("model", "patience")),
        eff_max=float(need("model", "eff_max")),
    )
    c = Cfg(
        site=site,
        window=win,
        truth=truth,
        nwp=nwp,
        lead_days=tuple(need("forecast", "lead_days")),
        wet_mm=float(need("forecast", "wet_mm")),
        heavy_mm=float(need("forecast", "heavy_mm")),
        model=model,
        paths=Paths((path.parent / own("data")).resolve(), data[donor] if donor else None),
        source=path,
        donor=donor,
    )
    errs = check(c)
    if errs:
        raise ValueError(f"{path}:\n  " + "\n  ".join(errs))
    return c


def check(c):
    errs = []
    s, w = c.site, c.window

    if not re.fullmatch(r"[a-z][a-z0-9_-]*", s.name):
        errs.append(f"site names must be lowercase letters, digits, - or _, as they go in URLs: {s.name}")
    if len(s.bbox) != 4:
        errs.append(f"sites.{s.name}.bbox needs 4 values: lat0, lat1, lon0, lon1")
    else:
        lat0, lat1, lon0, lon1 = s.bbox
        if not (lat0 < lat1 and lon0 < lon1):
            errs.append(f"sites.{s.name}.bbox not ordered: {s.bbox}")
        if not (lat0 <= s.lat <= lat1 and lon0 <= s.lon <= lon1):
            errs.append(f"sites.{s.name} ({s.lat}, {s.lon}) outside bbox {s.bbox}")
    if not 0 <= s.elev <= 6000:
        errs.append(f"sites.{s.name}.elev_m implausible: {s.elev}")
    try:
        ZoneInfo(s.tz)
    except (ZoneInfoNotFoundError, ValueError):
        errs.append(f"sites.{s.name}.tz unknown: {s.tz}")

    dates = [w.start, w.train_end, w.test_start, w.test_end, c.nwp.start]
    if not all(isinstance(d, date) for d in dates):
        errs.append("window dates and nwp.start must be bare TOML dates, e.g. 2026-04-01")
    else:
        if not (w.start < w.train_end < w.test_start <= w.test_end):
            errs.append("window must satisfy start < train_end < test_start <= test_end")
        if not (w.start <= c.nwp.start < w.train_end):
            errs.append("nwp.start must fall between window.start and window.train_end")
    if not w.wet or any(m not in range(1, 13) for m in w.wet):
        errs.append(f"window.wet_months invalid: {w.wet}")

    if c.truth.temp not in ("ghcnh", "iem", "merged"):
        errs.append(f"truth.temp must be ghcnh, iem or merged: {c.truth.temp}")
    if c.truth.rain not in ("station", "chirps"):
        errs.append(f"truth.rain must be station or chirps: {c.truth.rain}")
    if c.truth.chirps_flavor not in ("sat", "rnl"):
        errs.append(f"truth.chirps_flavor must be sat or rnl: {c.truth.chirps_flavor}")

    if not c.nwp.base or c.nwp.base in c.nwp.extra:
        errs.append("nwp.base must be set and must not appear in nwp.extra")
    if set(c.nwp.compare) & {c.nwp.base, *c.nwp.extra} or len(set(c.nwp.compare)) != len(c.nwp.compare):
        errs.append("nwp.compare must not repeat itself, nwp.base or nwp.extra")
    if not 7 <= c.nwp.chunk_days <= 366:
        errs.append(f"nwp.chunk_days must be within 7..366: {c.nwp.chunk_days}")

    # the previous-runs archive covers days 1-7
    leads = list(c.lead_days)
    if not leads or leads != sorted(set(leads)) or not all(1 <= d <= 7 for d in leads):
        errs.append(f"forecast.lead_days must be sorted, unique, within 1..7: {c.lead_days}")
    if not 0 < c.wet_mm < c.heavy_mm:
        errs.append("forecast thresholds must satisfy 0 < wet_mm < heavy_mm")

    m = c.model
    if m.seeds < 1 or m.hidden < 4 or m.max_epochs < 1 or m.patience < 1 or m.eff_max <= 0:
        errs.append("model settings out of range")
    return errs


def sites(c):
    # every site in the same file, this one first
    names = list(read(c.source)["sites"])
    return [c, *(load(c.source, n) for n in names if n != c.site.name)]


@functools.cache
def get():
    return load()
