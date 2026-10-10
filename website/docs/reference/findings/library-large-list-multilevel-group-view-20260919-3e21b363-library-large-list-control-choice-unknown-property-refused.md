---
title: "library.large-list.control-choice-unknown-property-refused"
surface: library
scope: large-list
question: control-choice-unknown-property-refused
probe_surface: library
state: open
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# library.large-list.control-choice-unknown-property-refused

- Probe surface: library
- Run: library-large-list-multilevel-group-view/20260919-3e21b363
- Question: NEGATIVE CONTROL: a MERGE naming a property SP.Field does not have is refused on LVChoice

## machine

- Outcome: `ABORTED`
- Evidence: LVChoice, LVNumber, LVDate arrived indexed, so the unindexed half of this probe cannot be measured and no write was sent. Clear the fixture indexes and re-paste

[All findings](../live-findings)
