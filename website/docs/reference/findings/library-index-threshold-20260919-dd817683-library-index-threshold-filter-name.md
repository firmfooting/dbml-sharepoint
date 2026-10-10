---
title: "library.index.threshold-filter-name"
surface: library
scope: index
question: threshold-filter-name
probe_surface: library
state: open
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# library.index.threshold-filter-name

- Probe surface: library
- Run: library-index-threshold/20260919-dd817683
- Question: Is a selective filter on Name (FileLeafRef) served past the threshold with no index on it

## machine

- Outcome: `ABORTED`
- Evidence: the fixture library holds 2000 of 5001 files, so no query here was asked past the threshold

[All findings](../live-findings)
