---
schema_version: 2
id: 4be9-6ae4-41de-e0cb
alias: t-set-version
type: test
status: passing
origin: TestSetVersion written 2026-10-30, plus the Makefile targets exercised on a scratch copy of the repository
created: 2026-10-30
rel_verifies: [4be9-6ae4-41db-88b2]
generator: model.py/2.4.0
checksum: bf8066120553
---

# Increments reset the lower parts, unknown parts and malformed or unchanged versions are refused, the new version gets a TODO changelog entry above the previous ones, the CLI leaves the file untouched on error, and make clean keeps build/ddd while removing the rest

<!-- rationale, detail, alternatives considered -->
