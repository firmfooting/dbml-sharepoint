---
title: "library.large-list.ui-group-by-indexed-column-folder-scoped"
surface: library
scope: large-list
question: ui-group-by-indexed-column-folder-scoped
probe_surface: library
state: open
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# library.large-list.ui-group-by-indexed-column-folder-scoped

- Probe surface: library
- Run: library-large-list-modern-view/20260919-605bd86a
- Question: Does scoping the grouped view inside a folder holding fewer than 5,000 files change the answer

## machine

- Outcome: `NOT ESTABLISHED`
- Evidence: This run cannot ask it. The question needs a folder holding fewer than 5,000 files inside a library holding more than 5,000, and neither permanent fixture has one: 'dbmlsp Probe PreIndex' holds 5100 contiguous files at its root and 'dbmlsp Probe LargeLib' holds 5,500, both by contract. Both fixture probes resume and verify from the newest file name and fail closed on a name their pattern does not match, so adding a folder here would leave a fixture that takes six pastes to build unverifiable by its owner. Answering this needs a large library built WITH folders, which is a fixture probe rather than a change to this one.

[All findings](../live-findings)
