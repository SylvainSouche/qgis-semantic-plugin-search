"""Download the plugin catalogue and the readmes, for one QGIS version.

Adapted from the original data/qgis_plugins.py fetcher (CamelCase, testable
transport). The catalogue comes from plugins.qgis.org; readmes are resolved
through the plugin GitHub repository, falling back to the package archive.

Usage:
    python pipeline/FetchCatalogue.py 4.2 --output-dir build
"""
from __future__ import annotations

import concurrent.futures
import io
import json
import os
import re
import sys
import threading
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


def defaultTransport(url: str, timeout: int = 30) -> bytes:
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
    with opener.open(request, timeout=timeout) as response:
        return response.read()


class CatalogueFetcher:
    """Downloads and parses the official catalogue for a QGIS version."""

    def __init__(self, transport=defaultTransport) -> None:
        self.transport = transport

    def catalogueUrl(self, version: str) -> str:
        return f"{BASE_URL}?{urllib.parse.urlencode({'qgis': version})}"

    def fetch(self, version: str, destination: Path) -> bytes:
        payload = self.transport(self.catalogueUrl(version))
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

    def fetchAll(self, records, outputDir: Path) -> dict[int, str]:  # noqa: ANN001
        """Write <safe-name>.md files and return pluginId -> readmeUrl."""
        outputDir.mkdir(parents=True, exist_ok=True)
        resolved: dict[int, str] = {}
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
                print(f"[{count}/{len(records)}] {record.name}: {url or 'no readme'}")
        return resolved

    def _resolve(self, record, outputDir: Path) -> str:  # noqa: ANN001
        destination = PathSafeName(record.name, outputDir)
        for url in self._githubUrls(record.repository):
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

    def _githubUrls(self, repository: str) -> list[str]:
        """Candidate readme URLs, cheapest first.

        raw.githubusercontent.com guesses cost no API quota; the api.github.com
        readme endpoint (one call, exact file name) is only consulted when the
        guesses all fail, keeping a full catalogue run far below the 5,000
        requests per hour installation limit.
        """
        match = re.match(r"https?://github\.com/([^/]+)/([^/#?]+)", repository.strip())
        if not match:
            return []
        owner, repo = match.groups()
        repo = repo.removesuffix(".git")
        raw = [
            f"https://raw.githubusercontent.com/{owner}/{repo}/HEAD/{fileName}"
            for fileName in ("README.md", "README.rst", "README.txt", "README")
        ]
        try:
            readme = json.loads(
                self.transport(f"https://api.github.com/repos/{owner}/{repo}/readme")
            )
            downloadUrl = readme.get("download_url")
            if downloadUrl and downloadUrl not in raw:
                raw.append(downloadUrl)
        except (Exception, ValueError):  # noqa: BLE001 - raw guesses may suffice
            pass
        return raw

    def _readmeFromArchive(self, downloadUrl: str, destination: Path) -> bool:
        try:
            archiveData = self.transport(downloadUrl, timeout=90)
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
    readmeUrls = ReadmeFetcher(connections=args.connections).fetchAll(
        records, buildDir / f"plugins-{args.version}"
    )
    urlsPath = buildDir / f"readme-urls-{args.version}.json"
    urlsPath.write_text(
        json.dumps(readmeUrls, indent=0, sort_keys=True), encoding="utf-8"
    )
    print(f"Readme URLs: {urlsPath} ({len(readmeUrls)} resolved)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

# @impl 0f87-6ae3-6986-4446
