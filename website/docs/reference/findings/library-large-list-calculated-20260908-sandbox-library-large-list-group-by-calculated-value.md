---
title: "library.large-list.group-by-calculated-value"
surface: library
scope: large-list
question: group-by-calculated-value
probe_surface: library
state: void
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# library.large-list.group-by-calculated-value

- Probe surface: library
- Run: library-large-list-calculated/20260908-sandbox
- Question: Is a group-by on LVCalc honoured, ignored or refused past 5,000 items

## machine

- Outcome: `VOID`
- Evidence: a group-by was not honoured on LVChoice, a plain single-value column, so an unhonoured group-by on LVCalc cannot be attributed to the column being calculated

[All findings](../live-findings)
