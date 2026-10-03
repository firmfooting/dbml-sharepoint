---
title: "library.index.threshold-filter-author"
surface: library
scope: index
question: threshold-filter-author
probe_surface: library
state: open
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# library.index.threshold-filter-author

- Probe surface: library
- Run: library-index-threshold/20260919-4cf09602
- Question: Is a zero-match filter on Author served past the threshold with no index on it

## machine

- Outcome: `ABORTED`
- Evidence: the fixture library holds 4000 of 5001 files, so no query here was asked past the threshold

[All findings](../live-findings)
