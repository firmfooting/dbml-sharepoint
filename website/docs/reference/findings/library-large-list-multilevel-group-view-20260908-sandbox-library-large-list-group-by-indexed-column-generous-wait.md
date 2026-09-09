---
title: "library.large-list.group-by-indexed-column-generous-wait"
surface: library
scope: large-list
question: group-by-indexed-column-generous-wait
probe_surface: library
state: void
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# library.large-list.group-by-indexed-column-generous-wait

- Probe surface: library
- Run: library-large-list-multilevel-group-view/20260908-sandbox
- Question: Is a group-by on the indexed LVChoice served when it is waited out for minutes rather than for one minute
- Voided by: library.large-list.control-missing-group-column-ungrouped

## machine

- Outcome: `REFUSED (threshold)`
- Evidence: before the index, the same query was REFUSED (threshold). The index write was INDEXED and $filter=LVChoice eq 'Alpha' was SERVED (page full, so the count is unreadable) after 1 attempt(s) and 212 ms. The grouped query was then re-sent over 12 attempt(s) and 176814 ms, against the roughly 61,000 ms #480 gave it: at 646 ms grouped REFUSED (threshold), filter SERVED (page full, so the count is unreadable); at 16266 ms grouped REFUSED (threshold), filter SERVED (page full, so the count is unreadable); at 32546 ms grouped REFUSED (threshold), filter SERVED (page full, so the count is unreadable); at 48610 ms grouped REFUSED (threshold), filter SERVED (page full, so the count is unreadable); at 64715 ms grouped REFUSED (threshold), filter SERVED (page full, so the count is unreadable); at 80727 ms grouped REFUSED (threshold), filter SERVED (page full, so the count is unreadable); at 97044 ms grouped REFUSED (threshold), filter SERVED (page full, so the count is unreadable); at 112975 ms grouped REFUSED (threshold), filter SERVED (page full, so the count is unreadable); at 129066 ms grouped REFUSED (threshold), filter SERVED (page full, so the count is unreadable); at 144795 ms grouped REFUSED (threshold), filter SERVED (page full, so the count is unreadable); at 160679 ms grouped REFUSED (threshold), filter SERVED (page full, so the count is unreadable); at 176814 ms grouped REFUSED (threshold), filter SERVED (page full, so the count is unreadable). Last reading: collapsed HTTP 500 returned 0 row(s) against a RowLimit of 100, labels \{"LVChoice":\[]}, grouping markers \[], dimensions honoured 0 of 1 on the collapsed rows (\[]) and 0 of 1 on the expanded rows (\[]), first row null; expanded HTTP 500 returned 0 row(s); the same query with no \<GroupBy> returned HTTP 200 with 100 row(s); ViewXml \<View>\<Query>\<GroupBy Collapse="TRUE">\<FieldRef Name="LVChoice"/>\</GroupBy>\</Query>\<ViewFields>\<FieldRef Name="FileLeafRef"/>\<FieldRef Name="LVNumber"/>\<FieldRef Name="LVChoice"/>\</ViewFields>\<RowLimit>100\</RowLimit>\</View>; collapsed body \{"odata.error":\{"code":"-2147024860, Microsoft.SharePoint.SPQueryThrottledException","message":\{"lang":"en-US","value":"The attempted operation is prohibited because it exceeds the list view threshold."}}}. The answer did not change over 176814 ms. That is a longer wait than #480 took and it is still a bounded one, so what it settles is that an index does not lift this group-by within that window, which is the strongest form the claim can take from one run.

[All findings](../live-findings)
