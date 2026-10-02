---
title: "library.large-list.index-is-per-column"
surface: library
scope: large-list
question: index-is-per-column
probe_surface: library
state: void
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# library.large-list.index-is-per-column

- Probe surface: library
- Run: library-large-list-index/20260919-1266a678
- Question: With one column indexed, is its filter served while an unindexed sibling column is still refused
- Voided by: library.large-list.control-unindexed-filter-refused, library.large-list.index-removes-filter-throttle

## machine

- Outcome: `NOT ESTABLISHED`
- Evidence: no indexed filter was served, so there is no served half to pair an unindexed sibling against

[All findings](../live-findings)
