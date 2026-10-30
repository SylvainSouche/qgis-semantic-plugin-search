"""Download the plugin catalogue and the readmes, for one QGIS version.

Adapted from the original data/qgis_plugins.py fetcher (CamelCase, testable
transport). The catalogue comes from plugins.qgis.org; readmes are resolved
through the plugin GitHub repository, falling back to the package archive.

Usage:
    python pipeline/FetchCatalogue.py 4.2 --output-dir build
"""
from __future__ import annotations

import concurrent.futures
import datetime
import gzip
import io
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from pipeline.PluginCatalogue import safePluginFileName  # noqa: E402

BASE_URL = "https://plugins.qgis.org/plugins/plugins.xml"
USER_AGENT = "QGIS-SemanticPluginSearch-Pipeline/1.0"
README_RE = re.compile(r"(^|/)README(?:\.(?:md|rst|txt|markdown))?$", re.I)
_threadLocal = threading.local()
# A readme is small; anything bigger is not worth downloading. Plugin
# packages above 25 MB are refused by plugins.qgis.org anyway.
MAX_README_BYTES = 2_000_000
MAX_ARCHIVE_BYTES = 25_000_000
# Wall clock budget for one download: urllib's timeout only bounds each
# socket read, so a server trickling bytes could otherwise hold a worker
# (and with all workers held, the whole run) indefinitely.
DOWNLOAD_DEADLINE = 60


# Readme text kept per plugin in the cache. The embedding uses a 4000 char
# excerpt after markdown noise is stripped; keeping more raw text leaves room
# for that stripping without storing whole manuals.
MAX_CACHED_README_CHARS = 32_000
# A miss can be a transient failure as much as a plugin without readme:
# misses are retried once they are this old, hits only on a new version.
MISS_RETRY_DAYS = 28


class ReadmeCache:
    """Readmes of the previous run, reused while a plugin is unchanged.

    One gzipped JSON file per universe, stored on the embeddings branch next
    to the databases (never downloaded by the plugin). An entry is reused
    when the plugin version and repository are those it was fetched for, so
    a weekly run only downloads the readmes of new or updated plugins.
    Plugins without a readme are cached too and retried after
    MISS_RETRY_DAYS, since a miss may also have been a transient failure.
    """

    def __init__(self, entries: dict[str, dict] | None = None) -> None:
        self.entries = dict(entries or {})

    @classmethod
    def load(cls, path: Path | None) -> ReadmeCache:
        if path is None or not path.is_file():
            return cls()
        try:
            with gzip.open(path, "rt", encoding="utf-8") as stream:
                document = json.load(stream)
        except (OSError, ValueError):
            return cls()  # unreadable cache: fetch everything, never fail the run
        return cls(document.get("plugins") or {})

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(path, "wt", encoding="utf-8") as stream:
            json.dump({"format": "readme-cache-v1", "plugins": self.entries}, stream)

    def hit(self, record, today: datetime.date | None = None) -> dict | None:  # noqa: ANN001
        entry = self.entries.get(str(record.pluginId))
        if not entry or entry.get("version") != record.version:
            return None
        if entry.get("repository", "") != (record.repository or ""):
            return None
        if not entry.get("url"):
            today = today or datetime.date.today()
            try:
                checked = datetime.date.fromisoformat(entry.get("checked", ""))
            except ValueError:
                return None
            if (today - checked).days >= MISS_RETRY_DAYS:
                return None
        return entry

    @staticmethod
    def entryFor(record, url: str, text: str, today: datetime.date | None = None) -> dict:  # noqa: ANN001
        return {
            "version": record.version,
            "repository": record.repository or "",
            "url": url,
            "text": text[:MAX_CACHED_README_CHARS],
            "checked": (today or datetime.date.today()).isoformat(),
        }


class DownloadTooLarge(RuntimeError):
    """A response exceeded its byte cap and was abandoned."""


def defaultTransport(
    url: str,
    timeout: int = 20,
    maxBytes: int = MAX_README_BYTES,
    deadline: float = DOWNLOAD_DEADLINE,
) -> bytes:
    headers = {"User-Agent": USER_AGENT}
    # On CI, GITHUB_TOKEN raises the api.github.com rate limit from 60 to
    # 5000 per hour; without it the readme resolution exhausts the quota.
    token = os.environ.get("GITHUB_TOKEN", "")
    if token and "api.github.com" in url:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    opener = getattr(_threadLocal, "opener", None)
    if opener is None:
        opener = urllib.request.build_opener()
        _threadLocal.opener = opener
    started = time.monotonic()
    with opener.open(request, timeout=timeout) as response:  # nosec B310 - https only
        declared = response.headers.get("Content-Length")
        if declared and declared.isdigit() and int(declared) > maxBytes:
            raise DownloadTooLarge(f"{url}: {declared} bytes declared > {maxBytes}")
        chunks = []
        received = 0
        while True:
            chunk = response.read(65536)
            if not chunk:
                return b"".join(chunks)
            received += len(chunk)
            if received > maxBytes:
                raise DownloadTooLarge(f"{url}: more than {maxBytes} bytes")
            if time.monotonic() - started > deadline:
                raise TimeoutError(f"{url}: not complete after {deadline}s")
            chunks.append(chunk)


class CatalogueFetcher:
    """Downloads and parses the official catalogue for a QGIS version."""

    def __init__(self, transport=defaultTransport) -> None:
        self.transport = transport

    def catalogueUrl(self, version: str) -> str:
        return f"{BASE_URL}?{urllib.parse.urlencode({'qgis': version})}"

    def fetch(self, version: str, destination: Path) -> bytes:
        payload = self.transport(
            self.catalogueUrl(version), maxBytes=200_000_000, deadline=600
        )
        root = ET.fromstring(payload)
        if root.tag != "plugins":
            raise ValueError(f"Unexpected catalogue root element: {root.tag!r}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)
        return payload


class ReadmeFetcher:
    """Resolves one readme per plugin, from repository or package archive."""

    def __init__(self, transport=defaultTransport, connections: int = 8) -> None:
        self.transport = transport
        self.connections = connections

    def fetchAll(
        self, records, outputDir: Path, cache: ReadmeCache | None = None  # noqa: ANN001
    ) -> dict[int, str]:
        """Write <safe-name>.md files and return pluginId -> readmeUrl.

        With a cache, unchanged plugins are served from it and only new or
        updated ones are fetched; the cache is then rewritten in place to
        hold exactly the current catalogue.
        """
        outputDir.mkdir(parents=True, exist_ok=True)
        resolved: dict[int, str] = {}
        fresh: dict[str, dict] = {}
        toFetch = []
        for record in records:
            entry = cache.hit(record) if cache is not None else None
            if entry is None:
                toFetch.append(record)
                continue
            fresh[str(record.pluginId)] = entry
            if entry.get("text"):
                PathSafeName(record.name, outputDir).write_text(entry["text"], encoding="utf-8")
            if entry.get("url"):
                resolved[record.pluginId] = entry["url"]
        print(
            f"Readmes: {len(records) - len(toFetch)} unchanged plugins from the cache, "
            f"{len(toFetch)} to fetch",
            flush=True,
        )
        records = toFetch
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.connections, thread_name_prefix="readme"
        ) as pool:
            futures = {
                pool.submit(self._resolve, record, outputDir): record
                for record in records
            }
            for count, future in enumerate(
                concurrent.futures.as_completed(futures), start=1
            ):
                record = futures[future]
                try:
                    url = future.result()
                except Exception:  # noqa: BLE001 - one plugin failing is not fatal
                    url = ""
                if url:
                    resolved[record.pluginId] = url
                destination = PathSafeName(record.name, outputDir)
                text = (
                    destination.read_text(encoding="utf-8", errors="replace")
                    if url and destination.is_file()
                    else ""
                )
                fresh[str(record.pluginId)] = ReadmeCache.entryFor(record, url, text)
                # Flushed: CI pipes stdout, and a block buffered log loses its
                # tail when a job is cancelled or times out.
                print(
                    f"[{count}/{len(records)}] {record.name}: {url or 'no readme'}",
                    flush=True,
                )
        if cache is not None:
            cache.entries = fresh
        return resolved

    def _resolve(self, record, outputDir: Path) -> str:  # noqa: ANN001
        destination = PathSafeName(record.name, outputDir)
        # Cheapest first: raw guesses cost no API quota; the API lookup is
        # only made when every guess failed.
        for candidates in (self._rawGuesses, self._apiReadmeUrl):
            for url in candidates(record.repository):
                try:
                    payload = self.transport(url)
                except Exception:  # noqa: BLE001 - try the next candidate
                    continue
                if payload.strip():
                    destination.write_bytes(payload)
                    return url
        if record.downloadUrl:
            text = self._readmeFromArchive(record.downloadUrl, destination)
            if text:
                return record.downloadUrl + " [archive]"
        return ""

    @staticmethod
    def _repositoryParts(repository: str) -> tuple[str, str] | None:
        match = re.match(r"https?://github\.com/([^/]+)/([^/#?]+)", repository.strip())
        if not match:
            return None
        owner, repo = match.groups()
        return owner, repo.removesuffix(".git")

    def _rawGuesses(self, repository: str) -> list[str]:
        """raw.githubusercontent.com guesses for the usual readme names."""
        parts = self._repositoryParts(repository)
        if parts is None:
            return []
        owner, repo = parts
        return [
            f"https://raw.githubusercontent.com/{owner}/{repo}/HEAD/{fileName}"
            for fileName in ("README.md", "README.rst", "README.txt", "README")
        ]

    def _apiReadmeUrl(self, repository: str) -> list[str]:
        """The exact readme URL from the GitHub API, only after the guesses failed.

        One call per plugin whose guesses all missed keeps a full catalogue
        run far below the hourly API quota of the workflow token.
        """
        parts = self._repositoryParts(repository)
        if parts is None:
            return []
        owner, repo = parts
        try:
            readme = json.loads(
                self.transport(f"https://api.github.com/repos/{owner}/{repo}/readme")
            )
        except Exception:  # noqa: BLE001 - no readme, private repo or quota
            return []
        downloadUrl = readme.get("download_url") if isinstance(readme, dict) else None
        return [downloadUrl] if downloadUrl else []

    def _readmeFromArchive(self, downloadUrl: str, destination: Path) -> bool:
        try:
            archiveData = self.transport(
                downloadUrl, maxBytes=MAX_ARCHIVE_BYTES, deadline=120
            )
            with zipfile.ZipFile(io.BytesIO(archiveData)) as archive:
                candidates = sorted(
                    (name for name in archive.namelist() if README_RE.search(name)),
                    key=lambda name: (
                        name.count("/"),
                        not name.lower().endswith(".md"),
                        name.lower(),
                    ),
                )
                for candidate in candidates:
                    payload = archive.read(candidate)
                    if payload.strip():
                        destination.write_bytes(payload)
                        return True
        except (Exception, zipfile.BadZipFile):  # noqa: BLE001
            return False
        return False


def PathSafeName(name: str, outputDir: Path | None) -> Path:  # noqa: N802
    path = Path(safePluginFileName(name) + ".md")
    return path if outputDir is None else outputDir / path


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", help='QGIS version filter, e.g. "4.2"')
    parser.add_argument("--output-dir", default="build", help="Build directory")
    parser.add_argument("--connections", type=int, default=8)
    parser.add_argument(
        "--readme-cache",
        default="",
        help="Gzipped readme cache to reuse and update (unchanged plugins are not fetched)",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Ignore the readme cache and fetch every readme (the cache is still rewritten)",
    )
    args = parser.parse_args(argv)

    buildDir = Path(args.output_dir)
    cataloguePath = buildDir / f"plugins-{args.version}.xml"
    fetcher = CatalogueFetcher()
    try:
        payload = fetcher.fetch(args.version, cataloguePath)
    except Exception as error:  # noqa: BLE001 - CLI boundary, print a clean message
        print(
            f"Fatal error: cannot fetch the catalogue for QGIS {args.version}: {error}",
            file=sys.stderr,
        )
        return 1

    from pipeline.PluginCatalogue import parseCatalogue

    records = parseCatalogue(payload)
    print(f"Catalogue: {cataloguePath} ({len(records)} plugins)")
    cachePath = Path(args.readme_cache) if args.readme_cache else None
    cache = ReadmeCache() if args.refresh else ReadmeCache.load(cachePath)
    readmeUrls = ReadmeFetcher(connections=args.connections).fetchAll(
        records, buildDir / f"plugins-{args.version}", cache if cachePath else None
    )
    if cachePath is not None:
        cache.save(cachePath)
        print(f"Readme cache: {cachePath} ({len(cache.entries)} plugins)")
    urlsPath = buildDir / f"readme-urls-{args.version}.json"
    urlsPath.write_text(
        json.dumps(readmeUrls, indent=0, sort_keys=True), encoding="utf-8"
    )
    print(f"Readme URLs: {urlsPath} ({len(readmeUrls)} resolved)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

# @impl 0f87-6ae3-6986-4446
# @impl 4be9-6ae3-f84a-d578
# @impl 4be9-6ae4-3a55-8652
