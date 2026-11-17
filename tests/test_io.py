import os
import time

import pytest
import requests

from gnostiq import io


class Resp:
    def __init__(self, status, body=b"payload"):
        self.status_code, self.content, self.text = status, body, body.decode()
        self.ok = 200 <= status < 300
        self.url = "https://example.test/x"


def scripted(monkeypatch, *responses):
    calls, script = [], list(responses)

    def get(url, params=None, headers=None, timeout=None):
        calls.append((url, params))
        r = script.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    monkeypatch.setattr(io.requests, "get", get)
    monkeypatch.setattr(io.time, "sleep", lambda s: None)
    return calls


def test_downloads_once_then_serves_from_cache(tmp_path, monkeypatch):
    calls = scripted(monkeypatch, Resp(200, b"first"))
    path = tmp_path / "sub" / "f.bin"
    assert io.fetch("https://example.test/x", path, params={"a": 1}) == path
    assert path.read_bytes() == b"first" and calls == [("https://example.test/x", {"a": 1})]
    io.fetch("https://example.test/x", path)
    assert len(calls) == 1
    assert not list(tmp_path.rglob("*.part"))


def test_stale_copy_is_refreshed(tmp_path, monkeypatch):
    path = tmp_path / "f.bin"
    path.write_bytes(b"old")
    os.utime(path, (time.time() - 7200, time.time() - 7200))
    calls = scripted(monkeypatch, Resp(200, b"new"))
    io.fetch("https://example.test/x", path, max_age=10_000)
    assert path.read_bytes() == b"old" and not calls
    io.fetch("https://example.test/x", path, max_age=3600)
    assert path.read_bytes() == b"new" and len(calls) == 1


@pytest.mark.parametrize("status", [400, 404])
def test_missing_resource_raises_without_retry(tmp_path, monkeypatch, status):
    calls = scripted(monkeypatch, Resp(status, b"no such variable"))
    with pytest.raises(io.Missing, match="no such variable"):
        io.fetch("https://example.test/x", tmp_path / "f.bin")
    assert len(calls) == 1 and not (tmp_path / "f.bin").exists()


def test_transient_errors_are_retried(tmp_path, monkeypatch):
    calls = scripted(monkeypatch, Resp(503), requests.ConnectionError("reset"), Resp(200, b"ok"))
    path = tmp_path / "f.bin"
    io.fetch("https://example.test/x", path)
    assert path.read_bytes() == b"ok" and len(calls) == 3


def test_gives_up_after_tries(tmp_path, monkeypatch):
    calls = scripted(monkeypatch, *[Resp(500)] * 3)
    with pytest.raises(requests.HTTPError):
        io.fetch("https://example.test/x", tmp_path / "f.bin", tries=3)
    assert len(calls) == 3


def test_falls_back_to_stale_copy_when_refresh_fails(tmp_path, monkeypatch):
    path = tmp_path / "f.bin"
    path.write_bytes(b"old")
    os.utime(path, (time.time() - 7200, time.time() - 7200))
    scripted(monkeypatch, *[Resp(500)] * 2)
    assert io.fetch("https://example.test/x", path, max_age=60, tries=2) == path
    assert path.read_bytes() == b"old"
