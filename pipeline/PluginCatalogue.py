"""Catalogue model and parsing shared by the fetch and build steps.

The catalogue is the official plugins.xml of plugins.qgis.org filtered by
QGIS version; one pyqgis_plugin element exists per plugin and version, so
parsing keeps the first occurrence of each plugin id, like the original
fetcher this pipeline was adapted from.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass


@dataclass(frozen=True)
class PluginRecord:
    """One plugin entry of the official catalogue."""

    pluginId: int
    name: str
    version: str
    description: str
    about: str
    tags: tuple[str, ...]
    repository: str
    homepage: str
    tracker: str
    downloadUrl: str
    fileName: str
    authorName: str
    qgisMinimum: str
    qgisMaximum: str
    experimental: bool
    deprecated: bool
    server: bool
    downloads: int
    averageVote: float
    ratingVotes: int
    updateDate: str

    def tagsText(self) -> str:
        return ", ".join(self.tags)


def safePluginFileName(name: str) -> str:
    """Filesystem safe name used for readme files, as in the fetcher."""
    cleaned = re.sub(r"[^\w.-]+", "_", name, flags=re.UNICODE).strip("._")
    return cleaned or "unnamed-plugin"


def parseCatalogue(xmlBytes: bytes) -> list[PluginRecord]:
    """Parse catalogue bytes into records, one per plugin id (first wins)."""
    root = ET.fromstring(xmlBytes)
    if root.tag != "plugins":
        raise ValueError(f"Unexpected catalogue root element: {root.tag!r}")
    records: dict[int, PluginRecord] = {}
    for element in root.findall("pyqgis_plugin"):
        record = _parsePluginElement(element)
        if record is None or record.pluginId in records:
            continue
        records[record.pluginId] = record
    return list(records.values())


def _text(element: ET.Element, tag: str) -> str:
    child = element.find(tag)
    return (child.text or "").strip() if child is not None else ""


def _parsePluginElement(element: ET.Element) -> PluginRecord | None:
    pluginId = element.get("plugin_id") or element.get("name")
    if not pluginId:
        return None
    try:
        numericId = int(element.get("plugin_id", pluginId))
    except ValueError:
        numericId = abs(hash(pluginId)) % (10**9)
    return PluginRecord(
        pluginId=numericId,
        name=element.get("name", pluginId),
        version=element.get("version", ""),
        description=_text(element, "description"),
        about=_text(element, "about"),
        tags=tuple(tag.strip() for tag in _text(element, "tags").split(",") if tag.strip()),
        repository=_text(element, "repository"),
        homepage=_text(element, "homepage"),
        tracker=_text(element, "tracker"),
        downloadUrl=_text(element, "download_url"),
        fileName=_text(element, "file_name"),
        authorName=_text(element, "author_name"),
        qgisMinimum=_text(element, "qgis_minimum_version"),
        qgisMaximum=_text(element, "qgis_maximum_version"),
        experimental=_text(element, "experimental").lower() == "true",
        deprecated=_text(element, "deprecated").lower() == "true",
        server=_text(element, "server").lower() == "true",
        downloads=_toInt(_text(element, "downloads")),
        averageVote=_toFloat(_text(element, "average_vote")),
        ratingVotes=_toInt(_text(element, "rating_votes")),
        updateDate=_text(element, "update_date"),
    )


def _toInt(raw: str) -> int:
    try:
        return int(float(raw)) if raw else 0
    except ValueError:
        return 0


def _toFloat(raw: str) -> float:
    try:
        return float(raw) if raw else 0.0
    except ValueError:
        return 0.0
