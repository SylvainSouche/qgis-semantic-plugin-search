"""Readme fetching on the GitHub side (pipeline/FetchCatalogue.py).

Regression: a QGIS 3.44 run stalled after 1792 of 3818 plugins with no
error. The fetcher called the GitHub API for every plugin, downloaded whole
plugin packages without a size cap, bounded only each socket read rather
than each download, and its block buffered progress lost the log tail.
"""
from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from pipeline import FetchCatalogue
from pipeline.FetchCatalogue import DownloadTooLarge, ReadmeFetcher


def record(name: str, repository: str = "", downloadUrl: str = "", pluginId: int = 1):
    return SimpleNamespace(
        name=name, repository=repository, downloadUrl=downloadUrl, pluginId=pluginId
    )


class ScriptedTransport:
    def __init__(self, responses: dict) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict]] = []

    def __call__(self, url: str, **options) -> bytes:  # noqa: ANN003
        self.calls.append((url, options))
        response = self.responses.get(url)
        if response is None or isinstance(response, Exception):
            raise response or RuntimeError(f"404 {url}")
        return response


REPO = "https://github.com/owner/plugin"
RAW = "https://raw.githubusercontent.com/owner/plugin/HEAD/"
API = "https://api.github.com/repos/owner/plugin/readme"


def test_raw_guess_hit_makes_no_api_call(tmp_path: Path):
    transport = ScriptedTransport({RAW + "README.md": b"# Plugin"})
    url = ReadmeFetcher(transport)._resolve(record("Plugin", REPO), tmp_path)
    assert url == RAW + "README.md"
    assert all("api.github.com" not in called for called, _ in transport.calls)


def test_api_is_consulted_only_after_every_raw_guess_failed(tmp_path: Path):
    exact = RAW + "docs/Readme.md"
    transport = ScriptedTransport(
        {API: json.dumps({"download_url": exact}).encode(), exact: b"text"}
    )
    url = ReadmeFetcher(transport)._resolve(record("Plugin", REPO), tmp_path)
    assert url == exact
    called = [called for called, _ in transport.calls]
    assert called.index(API) == 4, "four raw guesses first, then one API call"


def test_archive_fallback_is_size_capped(tmp_path: Path):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("plugin/README.md", "from the package")
    download = "https://plugins.qgis.org/plugins/x/version/1/download/"
    transport = ScriptedTransport({download: buffer.getvalue()})
    url = ReadmeFetcher(transport)._resolve(record("X", downloadUrl=download), tmp_path)
    assert url.endswith("[archive]")
    (_, options), = transport.calls
    assert options["maxBytes"] == FetchCatalogue.MAX_ARCHIVE_BYTES
    assert options["deadline"] <= 120


class FakeResponse:
    def __init__(self, chunks, length=None) -> None:  # noqa: ANN001
        self.chunks = list(chunks)
        self.headers = {"Content-Length": str(length)} if length is not None else {}

    def read(self, size: int) -> bytes:
        return self.chunks.pop(0) if self.chunks else b""

    def __enter__(self):  # noqa: ANN204
        return self

    def __exit__(self, *exc) -> None:  # noqa: ANN002
        return None


@pytest.fixture()
def opener(monkeypatch):
    holder = SimpleNamespace(response=None)
    fake = SimpleNamespace(open=lambda request, timeout: holder.response)
    monkeypatch.setattr(FetchCatalogue._threadLocal, "opener", fake, raising=False)
    return holder


def test_transport_refuses_a_declared_oversized_download(opener):
    opener.response = FakeResponse([b"x"], length=10_000)
    with pytest.raises(DownloadTooLarge):
        FetchCatalogue.defaultTransport("https://example.test/big", maxBytes=100)


def test_transport_stops_reading_past_the_cap(opener):
    opener.response = FakeResponse([b"x" * 60, b"x" * 60])
    with pytest.raises(DownloadTooLarge):
        FetchCatalogue.defaultTransport("https://example.test/big", maxBytes=100)


def test_transport_enforces_a_wall_clock_deadline(opener, monkeypatch):
    ticks = iter([0.0, 5.0, 100.0, 200.0])
    monkeypatch.setattr(FetchCatalogue.time, "monotonic", lambda: next(ticks))
    opener.response = FakeResponse([b"a", b"b", b"c"])
    with pytest.raises(TimeoutError):
        FetchCatalogue.defaultTransport("https://example.test/slow", deadline=60)


def test_transport_returns_the_whole_payload(opener):
    opener.response = FakeResponse([b"ab", b"cd"], length=4)
    assert FetchCatalogue.defaultTransport("https://example.test/ok") == b"abcd"


# ------------------------------------------------------------ readme cache

import datetime  # noqa: E402

from pipeline.FetchCatalogue import MISS_RETRY_DAYS, ReadmeCache  # noqa: E402


def versioned(name: str, version: str, pluginId: int, repository: str = REPO):
    return SimpleNamespace(
        name=name, version=version, repository=repository, downloadUrl="", pluginId=pluginId
    )


def test_unchanged_plugins_come_from_the_cache_and_changed_ones_are_fetched(tmp_path: Path):
    cachePath = tmp_path / "Readmes-4.json.gz"
    transport = ScriptedTransport({RAW + "README.md": b"# fresh"})
    first = ReadmeCache()
    ReadmeFetcher(transport).fetchAll([versioned("A", "1.0", 1)], tmp_path / "r1", first)
    first.save(cachePath)
    assert len(transport.calls) == 1

    transport.calls.clear()
    cache = ReadmeCache.load(cachePath)
    urls = ReadmeFetcher(transport).fetchAll([versioned("A", "1.0", 1)], tmp_path / "r2", cache)
    assert transport.calls == [], "unchanged plugin: no network"
    assert urls == {1: RAW + "README.md"}
    assert (tmp_path / "r2" / "A.md").read_text() == "# fresh"

    ReadmeFetcher(transport).fetchAll([versioned("A", "1.1", 1)], tmp_path / "r3", cache)
    assert transport.calls, "a new version is fetched again"
    assert cache.entries["1"]["version"] == "1.1"


def test_the_cache_holds_exactly_the_current_catalogue(tmp_path: Path):
    transport = ScriptedTransport({RAW + "README.md": b"# text"})
    cache = ReadmeCache()
    fetcher = ReadmeFetcher(transport)
    fetcher.fetchAll([versioned("A", "1", 1), versioned("B", "1", 2)], tmp_path / "a", cache)
    fetcher.fetchAll([versioned("B", "1", 2)], tmp_path / "b", cache)
    assert set(cache.entries) == {"2"}, "removed plugins drop out of the cache"


def test_misses_are_cached_then_retried_after_the_delay():
    record = versioned("NoReadme", "1", 7)
    today = datetime.date(2026, 11, 2)
    entry = ReadmeCache.entryFor(record, "", "", today=today)
    cache = ReadmeCache({"7": entry})
    assert cache.hit(record, today=today + datetime.timedelta(days=7)) is entry
    later = today + datetime.timedelta(days=MISS_RETRY_DAYS)
    assert cache.hit(record, today=later) is None


def test_a_changed_repository_or_unreadable_cache_means_fetching(tmp_path: Path):
    record = versioned("A", "1", 1)
    cache = ReadmeCache({"1": ReadmeCache.entryFor(record, RAW + "README.md", "x")})
    assert cache.hit(versioned("A", "1", 1, repository="https://github.com/new/home")) is None
    broken = tmp_path / "broken.json.gz"
    broken.write_bytes(b"not gzip")
    assert ReadmeCache.load(broken).entries == {}
