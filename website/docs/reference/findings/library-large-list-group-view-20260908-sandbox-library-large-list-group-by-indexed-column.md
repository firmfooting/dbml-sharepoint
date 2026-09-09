---
title: "library.large-list.group-by-indexed-column"
surface: library
scope: large-list
question: group-by-indexed-column
probe_surface: library
state: void
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# library.large-list.group-by-indexed-column

- Probe surface: library
- Run: library-large-list-group-view/20260908-sandbox
- Question: Is a group-by on LVChoice honoured, ignored or refused once the column is indexed
- Voided by: library.large-list.control-missing-group-column-ungrouped

## machine

- Outcome: `REFUSED (threshold)`
- Evidence: before the index, the same query was REFUSED (threshold). The index write was INDEXED. The OData filter LVChoice eq 'Alpha' was then SERVED (page full, so the count is unreadable) after 1 attempt(s) and 144 ms, which is the signal #478 used that the index had built. The grouped query, over 10 attempt(s) and 61083 ms: collapsed HTTP 500 returned 0 row(s) against a RowLimit of 100, labels \[], grouping markers \[], first row null; expanded HTTP 500 returned 0 row(s); the same query with no \<GroupBy> returned HTTP 200 with 100 row(s); ViewXml \<View>\<Query>\<GroupBy Collapse="TRUE">\<FieldRef Name="LVChoice"/>\</GroupBy>\</Query>\<ViewFields>\<FieldRef Name="FileLeafRef"/>\<FieldRef Name="LVNumber"/>\<FieldRef Name="LVChoice"/>\</ViewFields>\<RowLimit>100\</RowLimit>\</View>; collapsed body \{"odata.error":\{"code":"-2147024860, Microsoft.SharePoint.SPQueryThrottledException","message":\{"lang":"en-US","value":"The attempted operation is prohibited because it exceeds the list view threshold."}}}. The answer did not change with the index. SharePoint builds the index behind the flag, so a query still refused here does not establish that an index cannot lift a grouped throttle: re-paste in a few minutes, when the flag is already written, to take the after half alone.

[All findings](../live-findings)
