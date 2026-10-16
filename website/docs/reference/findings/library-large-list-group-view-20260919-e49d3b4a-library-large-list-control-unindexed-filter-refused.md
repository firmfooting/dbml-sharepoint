---
title: "library.large-list.control-unindexed-filter-refused"
surface: library
scope: large-list
question: control-unindexed-filter-refused
probe_surface: library
state: open
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# library.large-list.control-unindexed-filter-refused

- Probe surface: library
- Run: library-large-list-group-view/20260919-e49d3b4a
- Question: NEGATIVE CONTROL: a selective filter on an unindexed contract column is refused WITH the throttle signature

## machine

- Outcome: `ABORTED`
- Evidence: LVChoice arrived indexed, so the unindexed half of this probe cannot be measured and no write was sent. Clear the fixture indexes and re-paste

[All findings](../live-findings)
