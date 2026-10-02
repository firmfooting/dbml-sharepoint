---
title: "library.large-list.control-unindexed-filter-refused"
surface: library
scope: large-list
question: control-unindexed-filter-refused
probe_surface: library
state: failed
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# library.large-list.control-unindexed-filter-refused

- Probe surface: library
- Run: library-large-list-index/20260919-dc62b460
- Question: NEGATIVE CONTROL: a selective filter on an unindexed contract column is refused WITH the throttle signature

## machine

- Outcome: `CONTROL FAILED, METHOD VOID`
- Evidence: $filter=LVChoice eq 'Alpha' on 5500 file(s), matching 1375 of them: HTTP 200, SERVED (page full, so the count is unreadable). LVChoice: Indexed=true, AutoIndexed=false: \{"odata.nextLink":"\<sharepoint-url> Without a refusal here nothing served below is evidence of an index: the library may simply not be far enough past the threshold for this tenant to enforce it.

[All findings](../live-findings)
