---
title: "library.large-list.control-unindexed-filter-refused"
surface: library
scope: large-list
question: control-unindexed-filter-refused
probe_surface: library
state: open
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# library.large-list.control-unindexed-filter-refused

- Probe surface: library
- Run: library-large-list-calculated/20260919-a353a14d
- Question: NEGATIVE CONTROL: a selective filter on an unindexed contract column is refused WITH the throttle signature

## machine

- Outcome: `NOT ESTABLISHED`
- Evidence: every contract column read Indexed=true at the start of this run, so there is no unindexed column left to witness a throttle with. Run library-large-list-index-probe.js with REMOVE\_INDEXES\_AT\_END, then re-paste: flags were LVText: Indexed=true, AutoIndexed=false; LVNumber: Indexed=true, AutoIndexed=false; LVChoice: Indexed=true, AutoIndexed=false; LVDate: Indexed=true, AutoIndexed=false; LVMultiChoice: Indexed=false, AutoIndexed=false; LVLookup: Indexed=true, AutoIndexed=false; LVCalc: Indexed=false, AutoIndexed=false

[All findings](../live-findings)
