---
schema_version: 2
id: 4be9-6ae3-f4ad-b6ea
alias: req-qgis-network-stack
type: req
status: confirmed
origin: derived from con-qgis-repository-rules, 2026-10-30
created: 2026-10-30
rel_decided_by: [4be9-6ae3-f4ad-bf8b]
rel_refines: [0f87-6ae3-6970-f0a1]
generator: model.py/2.4.0
checksum: 0a789b68dff4
---

# Every download the plugin makes, release index, model, databases, readmes and icons, goes through the QGIS network stack so the user's proxy, SSL and authentication settings apply, bypassing the QGIS network cache, with the plugin code importing no other network library

<!-- rationale, detail, alternatives considered -->
