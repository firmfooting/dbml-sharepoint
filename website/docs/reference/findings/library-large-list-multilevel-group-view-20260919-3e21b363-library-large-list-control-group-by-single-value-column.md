---
title: "library.large-list.control-group-by-single-value-column"
surface: library
scope: large-list
question: control-group-by-single-value-column
probe_surface: library
state: open
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# library.large-list.control-group-by-single-value-column

- Probe surface: library
- Run: library-large-list-multilevel-group-view/20260919-3e21b363
- Question: Is a group-by on the unindexed LVChoice honoured, ignored or refused past 5,000 items

## machine

- Outcome: `ABORTED`
- Evidence: LVChoice, LVNumber, LVDate arrived indexed, so the unindexed half of this probe cannot be measured and no write was sent. Clear the fixture indexes and re-paste

[All findings](../live-findings)
