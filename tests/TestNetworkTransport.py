"""The QGIS network transport (QgisBridge.NetworkTransport) with stubbed
QGIS classes: downloads go through QgsBlockingNetworkRequest with the QGIS
cache bypassed, failures map to TransportError, and the byte cap cancels an
oversized download through the feedback object. The QGIS plugin repository
requires the QGIS network stack so proxy and authentication settings apply.
"""
from __future__ import annotations

import importlib
import sys
import types

import pytest

import tests.TestInstallerGateway  # noqa: F401 - installs the qgis stubs
from SemanticPluginSearch.Data.AssetGateways import TransportError


class FakeSignal:
    def __init__(self) -> None:
        self.slots = []

    def connect(self, slot) -> None:  # noqa: ANN001
        self.slots.append(slot)

    def emit(self, *args) -> None:  # noqa: ANN002
        for slot in self.slots:
            slot(*args)


class FakeFeedback:
    def __init__(self) -> None:
        self.cancelled = False

    def cancel(self) -> None:
        self.cancelled = True


class FakeReply:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def content(self) -> bytes:
        return self.payload


class FakeBlockingRequest:
    """Serves the class level script: (error code, payload, progress steps)."""

    class ErrorCode:
        NoError = 0
        NetworkError = 1

    script: tuple = (0, b"", [])
    calls: list = []

    def __init__(self) -> None:
        self.downloadProgress = FakeSignal()
        self._payload = b""

    def get(self, request, forceRefresh=False, feedback=None):  # noqa: ANN001, ANN201
        error, payload, steps = type(self).script
        type(self).calls.append((request.url, forceRefresh))
        for received in steps:
            self.downloadProgress.emit(received, -1)
            if feedback is not None and feedback.cancelled:
                return self.ErrorCode.NetworkError
        self._payload = payload
        return error

    def errorMessage(self) -> str:
        return "network unreachable"

    def reply(self) -> FakeReply:
        return FakeReply(self._payload)


class FakeUrl:
    def __init__(self, url: str) -> None:
        self.url = url


class FakeNetworkRequest:
    def __init__(self, url: FakeUrl) -> None:
        self.url = url.url
        self.headers = {}

    def setRawHeader(self, name: bytes, value: bytes) -> None:
        self.headers[name] = value


@pytest.fixture()
def transport(monkeypatch):
    core = sys.modules["qgis.core"]
    monkeypatch.setattr(core, "QgsBlockingNetworkRequest", FakeBlockingRequest, raising=False)
    monkeypatch.setattr(core, "QgsFeedback", FakeFeedback, raising=False)
    monkeypatch.setattr(sys.modules["qgis.PyQt.QtCore"], "QUrl", FakeUrl, raising=False)
    network = types.ModuleType("qgis.PyQt.QtNetwork")
    network.QNetworkRequest = FakeNetworkRequest
    monkeypatch.setitem(sys.modules, "qgis.PyQt.QtNetwork", network)
    sys.modules.pop("SemanticPluginSearch.QgisBridge.NetworkTransport", None)
    module = importlib.import_module("SemanticPluginSearch.QgisBridge.NetworkTransport")
    FakeBlockingRequest.calls = []
    yield module.qgisFetchUrl
    sys.modules.pop("SemanticPluginSearch.QgisBridge.NetworkTransport", None)


def test_success_returns_the_payload_and_bypasses_the_qgis_cache(transport):
    FakeBlockingRequest.script = (0, b"payload", [3, 7])
    assert transport("https://example.test/index.json") == b"payload"
    assert FakeBlockingRequest.calls == [("https://example.test/index.json", True)]


def test_network_errors_become_transport_errors(transport):
    FakeBlockingRequest.script = (1, b"", [])
    with pytest.raises(TransportError, match="network unreachable"):
        transport("https://example.test/index.json")


def test_oversized_downloads_are_cancelled(transport):
    FakeBlockingRequest.script = (0, b"x" * 100, [10, 60, 100])
    with pytest.raises(TransportError, match="too large"):
        transport("https://example.test/big", maxBytes=50)


def test_non_web_schemes_are_refused_before_any_request(transport):
    with pytest.raises(TransportError, match="unsupported URL scheme"):
        transport("file:///etc/passwd")
    assert FakeBlockingRequest.calls == []
