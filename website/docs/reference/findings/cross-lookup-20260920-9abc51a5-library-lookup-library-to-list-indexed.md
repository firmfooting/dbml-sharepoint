---
title: "library.lookup.library-to-list-indexed"
surface: library
scope: lookup
question: library-to-list-indexed
probe_surface: library
state: open
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# library.lookup.library-to-list-indexed

- Probe surface: library
- Run: cross-lookup/20260920-9abc51a5
- Question: Does Indexed=true stick on a lookup column held by a document library?

## machine

- Outcome: `NOT ESTABLISHED`
- Evidence: XLibToList already read Indexed=true before this run wrote anything, so a readback of true would say nothing about the write. threshold-index-probe.js measured SharePoint indexing a column on its own between two runs, so this is a live possibility. Re-run with CLEANUP = true.

[All findings](../live-findings)
