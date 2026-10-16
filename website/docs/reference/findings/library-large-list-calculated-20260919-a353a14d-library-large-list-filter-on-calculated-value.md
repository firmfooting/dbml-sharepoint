---
title: "library.large-list.filter-on-calculated-value"
surface: library
scope: large-list
question: filter-on-calculated-value
probe_surface: library
state: void
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# library.large-list.filter-on-calculated-value

- Probe surface: library
- Run: library-large-list-calculated/20260919-a353a14d
- Question: Is a selective $filter on LVCalc served or refused past 5,000 items

## machine

- Outcome: `VOID`
- Evidence: no unindexed contract column was refused with the throttle signature, so this library was not shown to be enforcing the threshold and a refusal here has no established cause

[All findings](../live-findings)
