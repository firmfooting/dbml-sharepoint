---
title: "library.large-list.default-view-renders-first-page"
surface: library
scope: large-list
question: default-view-renders-first-page
probe_surface: library
state: open
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# library.large-list.default-view-renders-first-page

- Probe surface: library
- Run: library-large-list-group-view/20260919-e49d3b4a
- Question: Does the library default view serve its first page past 5,000 items

## machine

- Outcome: `ABORTED`
- Evidence: LVChoice arrived indexed, so the unindexed half of this probe cannot be measured and no write was sent. Clear the fixture indexes and re-paste

[All findings](../live-findings)
