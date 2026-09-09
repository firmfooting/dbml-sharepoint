---
title: "library.large-list.preindex-group-by-indexed-column"
surface: library
scope: large-list
question: preindex-group-by-indexed-column
probe_surface: library
state: void
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# library.large-list.preindex-group-by-indexed-column

- Probe surface: library
- Run: library-large-list-preindex-group-view/20260908-sandbox
- Question: Is a group-by on PChoice, indexed before the library crossed 5,000 files, honoured, ignored or refused at this size
- Voided by: library.large-list.control-missing-group-column-ungrouped, library.large-list.control-preindex-group-by-narrowed-honoured

## machine

- Outcome: `REFUSED (threshold)`
- Evidence: PChoice: Indexed=true, AutoIndexed=false, stamped at 4900 file(s) on "2026-09-08T10:21:31.369Z", over 5100 file(s) and the four values \["Alpha","Beta","Gamma","Delta"]. The grouped query was sent 4 time(s) over 32582 ms: at 646 ms grouped REFUSED (threshold), filter SERVED (page full, so the count is unreadable); at 11250 ms grouped REFUSED (threshold), filter SERVED (page full, so the count is unreadable); at 22007 ms grouped REFUSED (threshold), filter SERVED (page full, so the count is unreadable); at 32581 ms grouped REFUSED (threshold), filter SERVED (page full, so the count is unreadable). Last reading: collapsed HTTP 500 returned 0 row(s) against a RowLimit of 100, labels \{"PChoice":\[]}, grouping markers \[], first row null; expanded HTTP 500 returned 0 row(s); the same query with no \<GroupBy> returned HTTP 200 with 100 row(s); ViewXml \<View>\<Query>\<GroupBy Collapse="TRUE">\<FieldRef Name="PChoice"/>\</GroupBy>\</Query>\<ViewFields>\<FieldRef Name="FileLeafRef"/>\<FieldRef Name="PChoice"/>\</ViewFields>\<RowLimit>100\</RowLimit>\</View>; collapsed body \{"odata.error":\{"code":"-2147024860, Microsoft.SharePoint.SPQueryThrottledException","message":\{"lang":"en-US","value":"The attempted operation is prohibited because it exceeds the list view threshold."}}}. #481 measured this same query refused on a column indexed AFTER the crossing. It is refused here too, on a column indexed before it, so the ordering does not change what an aggregation is given and the guidance about indexing before 5,000 items is about the filter rather than about the group-by. Two independently built fixtures now say the same thing.

[All findings](../live-findings)
