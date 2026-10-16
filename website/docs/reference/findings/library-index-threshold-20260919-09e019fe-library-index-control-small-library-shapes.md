---
title: "library.index.control-small-library-shapes"
surface: library
scope: index
question: control-small-library-shapes
probe_surface: library
state: open
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# library.index.control-small-library-shapes

- Probe surface: library
- Run: library-index-threshold/20260919-09e019fe
- Question: CONTROL: every filter parses and finds its target on a small library nothing throttles

## machine

- Outcome: `ABORTED`
- Evidence: the fixture library holds 0 of 5001 files, so no query here was asked past the threshold

[All findings](../live-findings)
