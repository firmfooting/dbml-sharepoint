---
title: "library.large-list.index-choice-column"
surface: library
scope: large-list
question: index-choice-column
probe_surface: library
state: open
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# library.large-list.index-choice-column

- Probe surface: library
- Run: library-large-list-index/20260919-1266a678
- Question: Does Indexed=true take on LVChoice (Choice) past 5,000 items

## machine

- Outcome: `NOT ESTABLISHED`
- Evidence: LVChoice already read Indexed=true before this run wrote anything, so a readback of true would say nothing about the write. threshold-index-probe.js measured SharePoint indexing a column on its own between two runs, so this is a live possibility. Set REMOVE\_INDEXES\_AT\_END, re-paste, then run again.

[All findings](../live-findings)
