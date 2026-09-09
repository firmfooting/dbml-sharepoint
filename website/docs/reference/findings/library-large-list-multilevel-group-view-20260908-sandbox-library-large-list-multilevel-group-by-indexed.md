---
title: "library.large-list.multilevel-group-by-indexed"
surface: library
scope: large-list
question: multilevel-group-by-indexed
probe_surface: library
state: void
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# library.large-list.multilevel-group-by-indexed

- Probe surface: library
- Run: library-large-list-multilevel-group-view/20260908-sandbox
- Question: Is a three-level group-by served once all three of its columns are indexed

## machine

- Outcome: `VOID`
- Evidence: the narrowed control did not hold, so a refusal here cannot be told from the server rejecting a three-FieldRef \<GroupBy>. Index writes: LVChoice INDEXED, LVNumber INDEXED, LVDate INDEXED

[All findings](../live-findings)
