---
schema_version: 2
id: 4be9-6ae4-3eac-a5b8
alias: t-model-pairing
type: test
status: passing
origin: TestModelPairing written during takeover, 2026-10-30; fails on the previous code with the reported AttributeError
created: 2026-10-30
rel_verifies: [4be9-6ae4-3eac-c78b]
generator: model.py/2.4.0
checksum: 1c77fbe4eb54
---

# The real engine reports its model id, a matching model validates and the search runs, a second validation reuses the loaded model, a missing model is not an error, and a different model is refused

<!-- rationale, detail, alternatives considered -->
