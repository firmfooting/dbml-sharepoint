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
- Run: library-large-list-group-view/20260919-e49d3b4a
- Question: Every contract column reads Indexed=false before this run writes anything

## machine

- Outcome: `ABORTED`
- Evidence: LVText: Indexed=true, AutoIndexed=false; LVNumber: Indexed=true, AutoIndexed=false; LVChoice: Indexed=true, AutoIndexed=false; LVDate: Indexed=true, AutoIndexed=false; LVMultiChoice: Indexed=false, AutoIndexed=false; LVLookup: Indexed=true, AutoIndexed=false; LVCalc: Indexed=false, AutoIndexed=false. Not clear: LVText, LVNumber, LVChoice, LVDate, LVLookup did not read Indexed=false. LVChoice is NOT unindexed, so question one cannot be asked at all: a group-by measured on it now would be an indexed group-by reported as an unindexed one. Run library-large-list-index-probe.js with REMOVE\_INDEXES\_AT\_END, then re-paste.

[All findings](../live-findings)
