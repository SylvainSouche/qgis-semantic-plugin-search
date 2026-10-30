---
schema_version: 2
id: 4be9-6ae4-4c75-dfef
alias: dec-error-popups
type: dec
status: recorded
origin: user rule, 2026-10-30 08:49: it is not acceptable to have to look at the message panel to get error messages, an error must produce a popup each time
created: 2026-10-30
generator: model.py/2.4.0
checksum: e0f694d96b90
---

# Every error opens a popup: the reporter's error path shows a non modal critical dialog parented to the active window in addition to the message bar, and the plugin installer's own critical log messages during an action are captured and raised as the action's error so they reach that popup; warnings stay in the message bar

<!-- rationale, detail, alternatives considered -->
