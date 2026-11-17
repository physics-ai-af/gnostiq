import tomllib
from pathlib import Path

from packaging.requirements import Requirement

ROOT = Path(__file__).resolve().parents[1]
META = tomllib.loads((ROOT / "pyproject.toml").read_text())


def by_name(reqs):
    return {r.name.lower(): r for r in reqs}


def read(name):
    lines = (ROOT / name).read_text().splitlines()
    return [Requirement(x) for x in lines if x.strip() and not x.startswith(("#", "-"))]


PIPFILE = tomllib.loads((ROOT / "Pipfile").read_text())
RUN = by_name(Requirement(x) for x in META["project"]["dependencies"])
DEV = by_name(Requirement(x) for x in META["dependency-groups"]["dev"])


def test_runtime_file_matches_pyproject():
    assert set(by_name(read("requirements.txt"))) == set(RUN)


def test_dev_file_adds_the_dev_group():
    assert "-r requirements.txt" in (ROOT / "requirements-dev.txt").read_text().splitlines()
    assert set(by_name(read("requirements-dev.txt"))) == set(DEV)


def test_pins_are_exact_and_inside_the_pyproject_ranges():
    for name, spec in (("requirements.txt", RUN), ("requirements-dev.txt", DEV)):
        for r in read(name):
            want = spec[r.name.lower()]
            (pin,) = r.specifier
            assert pin.operator == "==", r
            assert want.specifier.contains(pin.version), r
            assert str(r.marker) == str(want.marker), r


def test_cpu_torch_index_comes_with_torch():
    text = (ROOT / "requirements.txt").read_text()
    assert ("download.pytorch.org/whl/cpu" in text) == ("torch" in RUN)


def pipfile_pins(section):
    out = {}
    for name, v in PIPFILE[section].items():
        if name != "gnostiq":
            out[name.lower()] = v if isinstance(v, str) else v["version"]
    return out


def test_pipfile_matches_the_requirements_files():
    assert pipfile_pins("packages") == {r.name.lower(): str(r.specifier) for r in read("requirements.txt")}
    assert pipfile_pins("dev-packages") == {r.name.lower(): str(r.specifier) for r in read("requirements-dev.txt")}
    assert PIPFILE["packages"]["gnostiq"] == {"path": ".", "editable": True}


def test_pipfile_sends_torch_to_the_cpu_index():
    sources = {x["name"]: x["url"] for x in PIPFILE["source"]}
    torch = PIPFILE["packages"].get("torch")
    if torch is None:
        assert "pytorch-cpu" not in sources
    else:
        assert sources[torch["index"]] == "https://download.pytorch.org/whl/cpu"
