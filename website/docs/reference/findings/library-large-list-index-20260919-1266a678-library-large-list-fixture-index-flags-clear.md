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
- Run: library-large-list-index/20260919-1266a678
- Question: Every contract column reads Indexed=false before this run writes anything

## machine

- Outcome: `ALREADY INDEXED`
- Evidence: LVText: Indexed=true, AutoIndexed=false; LVNumber: Indexed=true, AutoIndexed=false; LVChoice: Indexed=true, AutoIndexed=false; LVDate: Indexed=true, AutoIndexed=false; LVMultiChoice: Indexed=false, AutoIndexed=false; LVLookup: Indexed=true, AutoIndexed=false; LVCalc: Indexed=false, AutoIndexed=false. LVText, LVNumber, LVChoice, LVDate, LVLookup arrived indexed, so the unindexed half of any before/after measurement on those columns cannot be taken this run. Set REMOVE\_INDEXES\_AT\_END, re-paste to put them back, then run again.

[All findings](../live-findings)
