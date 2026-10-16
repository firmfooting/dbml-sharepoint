---
title: "library.large-list.control-missing-group-column-ungrouped"
surface: library
scope: large-list
question: control-missing-group-column-ungrouped
probe_surface: library
state: open
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# library.large-list.control-missing-group-column-ungrouped

- Probe surface: library
- Run: library-large-list-group-view/20260919-e49d3b4a
- Question: Is a group-by naming a column the library does not hold ignored or refused past 5,000 items

## machine

- Outcome: `ABORTED`
- Evidence: LVChoice arrived indexed, so the unindexed half of this probe cannot be measured and no write was sent. Clear the fixture indexes and re-paste

[All findings](../live-findings)
