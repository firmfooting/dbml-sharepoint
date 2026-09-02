---
title: "scale.index.target-status-filter"
surface: scale
scope: index
question: target-status-filter
probe_surface: scale
state: open
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# scale.index.target-status-filter

- Probe surface: scale
- Run: threshold-index/20260827-272-guard
- Question: The INDEXED status filter on the lookup target

## machine

- Recorded as: `TGTSTA`
- Outcome: `NOT ESTABLISHED`
- Evidence: \[target holds 1] $filter=PickStatus eq 'Active', HTTP 200. Set SEED\_TARGET\_STATUS and re-paste: with nothing Active, PickCond is "" on every row and TGTCND / TGTFLT are about an empty column.

[All findings](../live-findings)
