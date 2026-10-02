---
title: "library.large-list.multilevel-group-by-field-order"
surface: library
scope: large-list
question: multilevel-group-by-field-order
probe_surface: library
state: open
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# library.large-list.multilevel-group-by-field-order

- Probe surface: library
- Run: library-large-list-multilevel-group-view/20260919-3e21b363
- Question: Does the order of the three \<FieldRef> children change what a three-level group-by is given

## machine

- Outcome: `ABORTED`
- Evidence: LVChoice, LVNumber, LVDate arrived indexed, so the unindexed half of this probe cannot be measured and no write was sent. Clear the fixture indexes and re-paste

[All findings](../live-findings)
