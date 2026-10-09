---
title: "library.large-list.index-number-column"
surface: library
scope: large-list
question: index-number-column
probe_surface: library
state: open
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# library.large-list.index-number-column

- Probe surface: library
- Run: library-large-list-multilevel-group-view/20260919-3e21b363
- Question: Does Indexed=true take on LVNumber (Number) past 5,000 items

## machine

- Outcome: `ABORTED`
- Evidence: LVChoice, LVNumber, LVDate arrived indexed, so the unindexed half of this probe cannot be measured and no write was sent. Clear the fixture indexes and re-paste

[All findings](../live-findings)
