---
title: "library.large-list.filtered-group-by-past-threshold"
surface: library
scope: large-list
question: filtered-group-by-past-threshold
probe_surface: library
state: open
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# library.large-list.filtered-group-by-past-threshold

- Probe surface: library
- Run: library-large-list-group-view/20260919-e49d3b4a
- Question: Is a group-by on the unindexed LVChoice served once a \<Where> on Id has narrowed the rows

## machine

- Outcome: `ABORTED`
- Evidence: LVChoice arrived indexed, so the unindexed half of this probe cannot be measured and no write was sent. Clear the fixture indexes and re-paste

[All findings](../live-findings)
