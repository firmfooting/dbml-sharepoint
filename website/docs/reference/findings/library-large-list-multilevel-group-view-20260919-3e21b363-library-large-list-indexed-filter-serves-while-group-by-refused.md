---
title: "library.large-list.indexed-filter-serves-while-group-by-refused"
surface: library
scope: large-list
question: indexed-filter-serves-while-group-by-refused
probe_surface: library
state: open
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# library.large-list.indexed-filter-serves-while-group-by-refused

- Probe surface: library
- Run: library-large-list-multilevel-group-view/20260919-3e21b363
- Question: At one moment, is the filter on the indexed LVChoice served while the group-by on it is refused

## machine

- Outcome: `ABORTED`
- Evidence: LVChoice, LVNumber, LVDate arrived indexed, so the unindexed half of this probe cannot be measured and no write was sent. Clear the fixture indexes and re-paste

[All findings](../live-findings)
