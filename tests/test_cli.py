import pytest
from conftest import add_nearby, write_cfg

from gnostiq import cfg, cli
from gnostiq.ingest import station


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.setenv("GNOSTIQ_CFG", str(write_cfg(tmp_path)))
    cfg.get.cache_clear()
    yield tmp_path
    cfg.get.cache_clear()


def test_requires_a_command(repo):
    with pytest.raises(SystemExit):
        cli.main([])


def test_unknown_source_is_rejected(repo):
    with pytest.raises(SystemExit, match="unknown source"):
        cli.main(["pull", "--only", "radar"])


def test_pull_passes_refresh_through(repo, monkeypatch):
    seen = []
    monkeypatch.setattr(station, "pull", lambda c, refresh=False: seen.append(refresh))
    cli.main(["pull", "--only", "station"])
    cli.main(["pull", "--only", "station", "--refresh"])
    assert seen == [False, True]


def test_creates_data_directories(repo, monkeypatch):
    monkeypatch.setattr(station, "pull", lambda c, refresh=False: None)
    cli.main(["pull", "--only", "station"])
    for d in ("raw", "interim", "processed", "models", "reports"):
        assert (repo / "data" / d).is_dir()


def test_build_without_data_says_what_to_run(repo):
    with pytest.raises(FileNotFoundError, match="gnostiq pull"):
        cli.main(["build"])


def test_site_option_picks_the_table(repo, monkeypatch):
    seen = []
    monkeypatch.setattr(station, "pull", lambda c, refresh=False: seen.append(c.site.name))
    add_nearby(repo)
    cli.main(["--site", "nearby", "pull", "--only", "station"])
    cli.main(["pull", "--only", "station"])
    assert seen == ["nearby", "jos"]


def test_a_site_on_borrowed_networks_cannot_build_or_train(repo):
    with pytest.raises(SystemExit, match="networks trained for jos"):
        add_nearby(repo)
        cli.main(["--site", "nearby", "build"])
