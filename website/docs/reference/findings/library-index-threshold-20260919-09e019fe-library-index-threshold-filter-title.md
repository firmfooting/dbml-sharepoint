---
title: "library.index.threshold-filter-title"
surface: library
scope: index
question: threshold-filter-title
probe_surface: library
state: open
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# library.index.threshold-filter-title

- Probe surface: library
- Run: library-index-threshold/20260919-09e019fe
- Question: Is a selective filter on Title served past the threshold with no index on it

## machine

- Outcome: `ABORTED`
- Evidence: the fixture library holds 0 of 5001 files, so no query here was asked past the threshold

[All findings](../live-findings)
