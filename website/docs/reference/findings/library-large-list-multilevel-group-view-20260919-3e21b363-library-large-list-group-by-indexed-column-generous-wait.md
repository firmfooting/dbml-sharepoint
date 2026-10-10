---
title: "library.large-list.group-by-indexed-column-generous-wait"
surface: library
scope: large-list
question: group-by-indexed-column-generous-wait
probe_surface: library
state: open
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# library.large-list.group-by-indexed-column-generous-wait

- Probe surface: library
- Run: library-large-list-multilevel-group-view/20260919-3e21b363
- Question: Is a group-by on the indexed LVChoice served when it is waited out for minutes rather than for one minute

## machine

- Outcome: `ABORTED`
- Evidence: LVChoice, LVNumber, LVDate arrived indexed, so the unindexed half of this probe cannot be measured and no write was sent. Clear the fixture indexes and re-paste

[All findings](../live-findings)
