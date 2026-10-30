"""Plain urllib HTTP transport for the GitHub side pipeline.

The plugin itself never uses this: inside QGIS every download goes through
QgsBlockingNetworkRequest (SemanticPluginSearch/QgisBridge/NetworkTransport.py)
so proxy and authentication settings are honoured. The pipeline runs on
GitHub Actions without QGIS, where urllib is the right tool.
"""
from __future__ import annotations

import urllib.error
import urllib.request

from SemanticPluginSearch.Data.AssetGateways import MAX_ASSET_BYTES, USER_AGENT, TransportError

DOWNLOAD_TIMEOUT = 60


def fetchUrl(url: str, timeout: int = DOWNLOAD_TIMEOUT, maxBytes: int = MAX_ASSET_BYTES) -> bytes:
    """Fetch an http(s) URL with a bounded read (never file:// or friends)."""
    if not url.lower().startswith(("http://", "https://")):
        raise TransportError(f"unsupported URL scheme: {url}")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        # The scheme is restricted to http(s) above.
        with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec B310
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
