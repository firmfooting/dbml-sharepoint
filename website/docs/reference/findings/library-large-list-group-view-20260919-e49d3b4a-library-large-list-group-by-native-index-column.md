---
title: "library.large-list.group-by-native-index-column"
surface: library
scope: large-list
question: group-by-native-index-column
probe_surface: library
state: open
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# library.large-list.group-by-native-index-column

- Probe surface: library
- Run: library-large-list-group-view/20260919-e49d3b4a
- Question: Is a group-by on Id, the one natively indexed column, served past 5,000 items

## machine

- Outcome: `ABORTED`
- Evidence: LVChoice arrived indexed, so the unindexed half of this probe cannot be measured and no write was sent. Clear the fixture indexes and re-paste

[All findings](../live-findings)
