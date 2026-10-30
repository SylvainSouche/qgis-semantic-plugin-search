"""HTTP transport through the QGIS network stack.

Every download of the plugin (release index, model, databases, readmes,
icons) goes through QgsBlockingNetworkRequest, so it honours the proxy,
SSL and authentication settings the user configured in QGIS, as the QGIS
plugin repository requires. QgsBlockingNetworkRequest is built to run on
worker threads and follows redirects itself (GitHub release downloads
redirect to a storage host).

The Data layer gateways receive this function as their transport; they stay
free of qgis and Qt imports.
"""
from __future__ import annotations

from qgis.core import QgsBlockingNetworkRequest, QgsFeedback
from qgis.PyQt.QtCore import QUrl
from qgis.PyQt.QtNetwork import QNetworkRequest

from ..Data.AssetGateways import MAX_ASSET_BYTES, USER_AGENT, TransportError

_ERROR_CODES = getattr(QgsBlockingNetworkRequest, "ErrorCode", QgsBlockingNetworkRequest)
NO_ERROR = _ERROR_CODES.NoError


def qgisFetchUrl(url: str, timeout: int = 60, maxBytes: int = MAX_ASSET_BYTES) -> bytes:
    """Fetch an http(s) URL through QGIS networking, with a size cap.

    The timeout argument is accepted for interface compatibility; QGIS
    applies its own network timeout setting. The QGIS network cache is
    bypassed: the plugin keeps its own verified caches, and a cached index
    would hide new releases.
    """
    del timeout
    if not url.lower().startswith(("http://", "https://")):
        raise TransportError(f"unsupported URL scheme: {url}")
    request = QNetworkRequest(QUrl(url))
    request.setRawHeader(b"User-Agent", USER_AGENT.encode("ascii"))
    feedback = QgsFeedback()
    blocking = QgsBlockingNetworkRequest()
    tooLarge: list[int] = []

    def onProgress(received: int, _total: int) -> None:
        if received > maxBytes and not tooLarge:
            tooLarge.append(received)
            feedback.cancel()

    blocking.downloadProgress.connect(onProgress)
    error = blocking.get(request, True, feedback)
    if tooLarge:
        raise TransportError(f"download too large for {url}: {tooLarge[0]} > {maxBytes}")
    if error != NO_ERROR:
        raise TransportError(f"{url}: {blocking.errorMessage()}")
    payload = bytes(blocking.reply().content())
    if len(payload) > maxBytes:
        raise TransportError(f"download too large for {url}: {len(payload)} > {maxBytes}")
    return payload
# @impl 4be9-6ae3-f4ad-b6ea
