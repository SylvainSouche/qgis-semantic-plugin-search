"""HTTP access to the project published assets and readmes.

Both gateways use only urllib, so the plugin needs nothing beyond the
standard library for its network layer. The transport is injectable for
tests (the fixture transport serves file:// style content from memory).

This module is part of the Data layer: it must import neither qgis nor Qt.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

from ..Domain.Entities import PluginInfo, RemoteFile, RemoteIndex, UniverseRelease
from ..Domain.Ports import AssetGateway, ReadmeGateway

INDEX_FORMAT = "qgis-semantic-search-index-v1"
USER_AGENT = "QGIS-SemanticPluginSearch"
DOWNLOAD_TIMEOUT = 60
MAX_README_BYTES = 400_000
MAX_ASSET_BYTES = 50_000_000


class TransportError(RuntimeError):
    """A network transfer failed."""


class ChecksumMismatch(TransportError):
    """A downloaded file does not match its published checksum or size."""


class IndexFormatError(ValueError):
    """The published index file does not match the expected format."""


class ReadmeUnavailable(LookupError):
    """No readme could be retrieved for a plugin."""


def fetchUrl(url: str, timeout: int = DOWNLOAD_TIMEOUT, maxBytes: int = MAX_ASSET_BYTES) -> bytes:
    """Fetch an http(s) URL with a bounded read (never file:// or friends)."""
    if not url.lower().startswith(("http://", "https://")):
        raise TransportError(f"unsupported URL scheme: {url}")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            chunks = []
            received = 0
            while True:
                chunk = response.read(65536)
                if not chunk:
                    break
                received += len(chunk)
                if received > maxBytes:
                    raise TransportError(
                        f"download too large for {url}: {received} > {maxBytes}"
                    )
                chunks.append(chunk)
            return b"".join(chunks)
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise TransportError(f"{url}: {error}") from error


def parseIndexDocument(document: bytes | dict) -> RemoteIndex:
    """Parse and validate an index.json document."""
    data = document if isinstance(document, dict) else json.loads(document)
    if data.get("format") != INDEX_FORMAT:
        raise IndexFormatError(f"unsupported index format: {data.get('format')!r}")
    modelData = data.get("model") or {}
    model = RemoteFile(
        url=str(modelData.get("url", "")),
        sha256=str(modelData.get("sha256", "")),
        bytes=int(modelData.get("bytes", 0)),
    )
    universes: dict[str, UniverseRelease] = {}
    for key, release in (data.get("universes") or {}).items():
        database = RemoteFile(
            url=str(release.get("url", "")),
            sha256=str(release.get("sha256", "")),
            bytes=int(release.get("bytes", 0)),
        )
        universes[str(key)] = UniverseRelease(
            database=database,
            buildStamp=str(release.get("build_stamp", "")),
            pluginCount=int(release.get("plugin_count", 0)),
        )
    return RemoteIndex(
        generatedAt=str(data.get("generated_at", "")),
        model=model,
        modelId=str(modelData.get("model_id", "")),
        modelDim=int(modelData.get("dim", 0)),
        universes=universes,
    )


class HttpAssetGateway(AssetGateway):
    """Concrete index fetching gateway; the index URL comes from settings."""

    def __init__(self, indexUrl: str, transport=fetchUrl) -> None:
        self.indexUrl = indexUrl
        self.transport = transport
        self.downloader = _VerifiedDownloader(transport)

    def fetchIndex(self) -> RemoteIndex:
        return parseIndexDocument(self.transport(self.indexUrl))

    def downloadVerified(self, remoteFile: RemoteFile, destination: Path) -> None:
        self.downloader.downloadVerified(remoteFile, destination)


class _VerifiedDownloader:
    """Checksum verified, atomic file downloads with a hard size cap."""

    MAX_ASSET_BYTES = 50_000_000

    def __init__(self, transport=fetchUrl, maxBytes: int = MAX_ASSET_BYTES) -> None:
        self.transport = transport
        self.maxBytes = maxBytes

    def downloadVerified(self, remoteFile: RemoteFile, destination: Path) -> None:
        payload = self.transport(remoteFile.url, maxBytes=self.maxBytes)
        if len(payload) > self.maxBytes:
            raise TransportError(
                f"download too large for {remoteFile.url}:"
                f" {len(payload)} > {self.maxBytes}"
            )
        if remoteFile.sha256:
            digest = hashlib.sha256(payload).hexdigest()
            if digest != remoteFile.sha256:
                raise ChecksumMismatch(
                    f"checksum mismatch for {remoteFile.url}:"
                    f" {digest} != {remoteFile.sha256}"
                )
        if remoteFile.bytes and len(payload) != remoteFile.bytes:
            raise ChecksumMismatch(
                f"size mismatch for {remoteFile.url}:"
                f" {len(payload)} != {remoteFile.bytes}"
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        handle, temporaryName = tempfile.mkstemp(
            dir=str(destination.parent), prefix=destination.name + "."
        )
        try:
            with os.fdopen(handle, "wb") as stream:
                stream.write(payload)
            os.replace(temporaryName, destination)
        except BaseException:
            Path(temporaryName).unlink(missing_ok=True)
            raise


class HttpIconGateway:
    """Fetches plugin icons with a local disk cache and in memory hits."""

    MAX_ICON_BYTES = 300_000

    def __init__(self, cacheDir: Path, transport=fetchUrl) -> None:
        self.cacheDir = Path(cacheDir)
        self.cacheDir.mkdir(parents=True, exist_ok=True)
        self.transport = transport
        self.cache: dict[str, bytes] = {}

    def fetchIcon(self, url: str) -> bytes:
        """Return the icon bytes for url, or raise for missing/invalid icons."""
        if url in self.cache:
            return self.cache[url]
        path = self._pathFor(url)
        if path.is_file():
            payload = path.read_bytes()
        else:
            payload = self.transport(url, maxBytes=self.MAX_ICON_BYTES)
            _assertImage(payload, url)
            path.write_bytes(payload)
        self.cache[url] = payload
        return payload

    def _pathFor(self, url: str) -> Path:
        import hashlib

        suffix = Path(url.split("?")[0]).suffix.lower()
        if suffix not in (".png", ".jpg", ".jpeg", ".gif", ".svg"):
            suffix = ".png"
        return self.cacheDir / (hashlib.sha256(url.encode()).hexdigest() + suffix)


def _assertImage(payload: bytes, url: str) -> None:
    signatures = (b"\x89PNG", b"\xff\xd8", b"GIF87a", b"GIF89a", b"<?xml", b"<svg")
    if not payload or not payload.startswith(signatures):
        raise ValueError(f"not an image: {url}")


class HttpReadmeGateway(ReadmeGateway):
    """Fetches readme text, preferring the URL resolved by the pipeline."""

    def __init__(self, transport=fetchUrl, maxBytes: int = MAX_README_BYTES) -> None:
        self.transport = transport
        self.maxBytes = maxBytes
        self.cache: dict[int, str] = {}

    def fetchReadme(self, info: PluginInfo) -> str:
        if info.pluginId in self.cache:
            return self.cache[info.pluginId]
        for url in self._candidateUrls(info):
            try:
                payload = self.transport(url, maxBytes=self.maxBytes)
            except TransportError:
                continue
            if payload:
                text = payload[: self.maxBytes].decode("utf-8", errors="replace")
                self.cache[info.pluginId] = text
                return text
        raise ReadmeUnavailable(info.name)

    def _candidateUrls(self, info: PluginInfo) -> list[str]:
        candidates = []
        if info.readmeUrl:
            candidates.append(info.readmeUrl)
        if info.repository.startswith("http"):
            base = info.repository.rstrip("/").removesuffix(".git")
            candidates.append(f"{base}/raw/HEAD/README.md")
        return candidates

# @impl 0f87-6ae3-6985-9c48
