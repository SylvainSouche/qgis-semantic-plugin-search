---
schema_version: 2
id: 4be9-6ae4-3eac-c78b
alias: req-model-pairing
type: req
status: confirmed
origin: derived from dec-review-two-fixes and obs-pairing-attribute-error, 2026-10-30
created: 2026-10-30
rel_decided_by: [4be9-6ae4-3eac-756b]
rel_refines: [0f87-6ae3-6970-f0a1]
generator: model.py/2.4.0
checksum: be8d9b5068ff
---

# A new embeddings database is activated only when the cached model's id matches the database's model id, reloading the model file once when the loaded model differs; with no model yet the search waits without error, and a mismatch pauses search with a message

<!-- rationale, detail, alternatives considered -->
