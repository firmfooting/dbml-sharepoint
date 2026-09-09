---
title: "library.large-list.group-by-native-index-column"
surface: library
scope: large-list
question: group-by-native-index-column
probe_surface: library
state: void
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# library.large-list.group-by-native-index-column

- Probe surface: library
- Run: library-large-list-group-view/20260908-sandbox
- Question: Is a group-by on Id, the one natively indexed column, served past 5,000 items
- Voided by: library.large-list.control-missing-group-column-ungrouped

## machine

- Outcome: `REFUSED (threshold)`
- Evidence: collapsed HTTP 500 returned 0 row(s) against a RowLimit of 100, labels \[], grouping markers \[], first row null; expanded HTTP 500 returned 0 row(s); the same query with no \<GroupBy> returned HTTP 200 with 100 row(s); ViewXml \<View>\<Query>\<GroupBy Collapse="TRUE">\<FieldRef Name="ID"/>\</GroupBy>\</Query>\<ViewFields>\<FieldRef Name="FileLeafRef"/>\<FieldRef Name="LVNumber"/>\<FieldRef Name="ID"/>\</ViewFields>\<RowLimit>100\</RowLimit>\</View>; collapsed body \{"odata.error":\{"code":"-2147024860, Microsoft.SharePoint.SPQueryThrottledException","message":\{"lang":"en-US","value":"The attempted operation is prohibited because it exceeds the list view threshold."}}}. Id is natively indexed on this library and nothing else is (library-index-threshold-probe.js, 2026-09-08), so this is an INDEXED group-by taken with no write at all. Every file carries its own Id, so an honoured grouping here is one group per row and the 100 RowLimit is what bounds the answer: the row count is a page of groups and is not a distinct-value count. Read this beside the two questions below: if an indexed group-by is not served either, an index is not what a group-by past the threshold wants.

[All findings](../live-findings)
