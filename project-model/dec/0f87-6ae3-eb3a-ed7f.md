---
schema_version: 2
id: 0f87-6ae3-eb3a-ed7f
alias: dec-spread-schedule
type: dec
status: recorded
origin: 2026-10-30, resolving obs-weekly-parallel-load
created: 2026-10-30
rel_resolves: [0f87-6ae3-eb3a-4d77]
generator: model.py/2.4.0
checksum: 0275cb6a6966
---

# The schedule fires Monday for QGIS 3.44 and Tuesday for QGIS 4.2, the matrix is planned from the triggering cron, and the publish step merges the freshly built universes with the carried over entries of the previous index so every publish stays complete; manual dispatches build both universes

<!-- rationale, detail, alternatives considered -->
