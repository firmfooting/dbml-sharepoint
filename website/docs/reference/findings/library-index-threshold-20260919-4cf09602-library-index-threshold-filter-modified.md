---
title: "library.index.threshold-filter-modified"
surface: library
scope: index
question: threshold-filter-modified
probe_surface: library
state: open
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# library.index.threshold-filter-modified

- Probe surface: library
- Run: library-index-threshold/20260919-4cf09602
- Question: Is a selective filter on Modified served past the threshold with no index on it

## machine

- Outcome: `ABORTED`
- Evidence: the fixture library holds 4000 of 5001 files, so no query here was asked past the threshold

[All findings](../live-findings)
