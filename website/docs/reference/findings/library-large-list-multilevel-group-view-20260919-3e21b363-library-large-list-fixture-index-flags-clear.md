---
title: "library.large-list.fixture-index-flags-clear"
surface: library
scope: large-list
question: fixture-index-flags-clear
probe_surface: library
state: open
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# library.large-list.fixture-index-flags-clear

- Probe surface: library
- Run: library-large-list-multilevel-group-view/20260919-3e21b363
- Question: Every contract column reads Indexed=false before this run writes anything

## machine

- Outcome: `ABORTED`
- Evidence: LVText: Indexed=true, AutoIndexed=false; LVNumber: Indexed=true, AutoIndexed=false; LVChoice: Indexed=true, AutoIndexed=false; LVDate: Indexed=true, AutoIndexed=false; LVMultiChoice: Indexed=false, AutoIndexed=false; LVLookup: Indexed=true, AutoIndexed=false; LVCalc: Indexed=false, AutoIndexed=false. Not clear: LVText, LVNumber, LVChoice, LVDate, LVLookup did not read Indexed=false. LVChoice, LVNumber, LVDate arrived indexed, so the before half of the grouped questions cannot be measured at all: a group-by taken on them now would be an indexed reading reported as an unindexed one. Run library-large-list-index-probe.js with REMOVE\_INDEXES\_AT\_END, then re-paste.

[All findings](../live-findings)
