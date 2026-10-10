---
title: "library.large-list.index-removes-filter-throttle"
surface: library
scope: large-list
question: index-removes-filter-throttle
probe_surface: library
state: void
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# library.large-list.index-removes-filter-throttle

- Probe surface: library
- Run: library-large-list-index/20260919-dc62b460
- Question: On one column, does a selective $filter go from refused to served once the column is indexed
- Voided by: library.large-list.control-unindexed-filter-refused

## machine

- Outcome: `NOT ESTABLISHED`
- Evidence: neither LVNumber nor LVText both started unindexed and took an index (LVNumber: NOT ESTABLISHED, LVText: NOT ESTABLISHED), so there is no column here whose before and after states are both measurable

[All findings](../live-findings)
