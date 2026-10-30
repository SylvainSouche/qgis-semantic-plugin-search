---
schema_version: 2
id: 4be9-6ae4-41db-fd2d
alias: dec-make-dist-version
type: dec
status: recorded
origin: user request, 2026-10-30 08:04: make clean must keep the model tooling, rename make package to make dist, add make version VERSION=x.y.z and make increment inc=maj|min|rel
created: 2026-10-30
generator: model.py/2.4.0
checksum: 9ff63f8914fe
---

# make package becomes make dist, matching its destination directory; make version VERSION=x.y.z and make increment inc=maj|min|rel set the metadata version through tools/SetVersion.py and open a TODO changelog entry that the repository rules test refuses until written; make clean keeps build/ddd and its pyc cleanup works with GNU find

<!-- rationale, detail, alternatives considered -->
