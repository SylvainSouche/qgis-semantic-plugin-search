---
schema_version: 2
id: 4be9-6ae3-f4c1-6adf
alias: t-network-transport
type: test
status: passing
origin: TestNetworkTransport written during takeover, 2026-10-30
created: 2026-10-30
rel_verifies: [4be9-6ae3-f4ad-b6ea]
generator: model.py/2.4.0
checksum: 70d939736add
---

# With stubbed QGIS network classes a download returns its payload with the QGIS cache bypassed, network errors become TransportError, an oversized download is cancelled, a non web scheme is refused before any request, and a source scan finds no network library import in the plugin

<!-- rationale, detail, alternatives considered -->
