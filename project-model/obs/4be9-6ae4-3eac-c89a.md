---
schema_version: 2
id: 4be9-6ae4-3eac-c89a
alias: obs-pairing-attribute-error
type: obs
status: recorded
origin: user report from QGIS, 2026-10-30 07:50, after the first embeddings branch build
created: 2026-10-30
rel_raised_by: [0f87-6ae3-e6f9-5a9f]
generator: model.py/2.4.0
checksum: 42e606324fa6
---

# On every database update QGIS reported that the embedding model does not match the database because StaticEmbeddingEngine has no modelId; since 0.3.0 the pairing check in PluginEntry therefore failed whenever a model was loaded and search never activated; the suite cannot import PluginEntry and every fake engine had a modelId

<!-- rationale, detail, alternatives considered -->
