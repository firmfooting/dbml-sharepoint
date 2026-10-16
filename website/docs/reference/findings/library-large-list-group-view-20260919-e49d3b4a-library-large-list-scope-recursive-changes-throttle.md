---
title: "library.large-list.scope-recursive-changes-throttle"
surface: library
scope: large-list
question: scope-recursive-changes-throttle
probe_surface: library
state: open
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# library.large-list.scope-recursive-changes-throttle

- Probe surface: library
- Run: library-large-list-group-view/20260919-e49d3b4a
- Question: Do Scope="Recursive" and Scope="RecursiveAll" change what a flat and a grouped query are given

## machine

- Outcome: `ABORTED`
- Evidence: LVChoice arrived indexed, so the unindexed half of this probe cannot be measured and no write was sent. Clear the fixture indexes and re-paste

[All findings](../live-findings)
