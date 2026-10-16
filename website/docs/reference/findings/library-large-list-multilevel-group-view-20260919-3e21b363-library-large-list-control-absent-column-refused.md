---
title: "library.large-list.control-absent-column-refused"
surface: library
scope: large-list
question: control-absent-column-refused
probe_surface: library
state: open
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# library.large-list.control-absent-column-refused

- Probe surface: library
- Run: library-large-list-multilevel-group-view/20260919-3e21b363
- Question: NEGATIVE CONTROL: a filter naming a column the library does not hold is refused WITHOUT the throttle signature

## machine

- Outcome: `ABORTED`
- Evidence: LVChoice, LVNumber, LVDate arrived indexed, so the unindexed half of this probe cannot be measured and no write was sent. Clear the fixture indexes and re-paste

[All findings](../live-findings)
