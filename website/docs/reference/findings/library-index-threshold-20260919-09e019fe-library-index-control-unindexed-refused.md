---
title: "library.index.control-unindexed-refused"
surface: library
scope: index
question: control-unindexed-refused
probe_surface: library
state: open
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# library.index.control-unindexed-refused

- Probe surface: library
- Run: library-index-threshold/20260919-09e019fe
- Question: NEGATIVE CONTROL: a selective filter on an unindexed probe-owned Text column is refused past the threshold

## machine

- Outcome: `ABORTED`
- Evidence: the fixture library holds 0 of 5001 files, so no query here was asked past the threshold

[All findings](../live-findings)
