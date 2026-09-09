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
- Run: library-large-list-preindex-group-view/20260908-sandbox-run2
- Question: Is a group-by on Id, the one natively indexed column, served past 5,000 items
- Voided by: library.large-list.control-missing-group-column-ungrouped, library.large-list.control-preindex-group-by-narrowed-honoured

## machine

- Outcome: `REFUSED (threshold)`
- Evidence: Id is natively indexed on every list and library (library-index-threshold-probe.js, 2026-09-08), and no write in this run touched it: collapsed HTTP 500 returned 0 row(s) against a RowLimit of 100, labels \{"ID":\[]}, grouping markers \[], first row null; expanded HTTP 500 returned 0 row(s); the same query with no \<GroupBy> returned HTTP 200 with 100 row(s); ViewXml \<View>\<Query>\<GroupBy Collapse="TRUE">\<FieldRef Name="ID"/>\</GroupBy>\</Query>\<ViewFields>\<FieldRef Name="FileLeafRef"/>\<FieldRef Name="PChoice"/>\</ViewFields>\<RowLimit>100\</RowLimit>\</View>; collapsed body \{"odata.error":\{"code":"-2147024860, Microsoft.SharePoint.SPQueryThrottledException","message":\{"lang":"en-US","value":"The attempted operation is prohibited because it exceeds the list view threshold."}}}. #480 measured the same refusal on the other fixture. A native index does not lift a group-by either, on either library, which is the reading the crux row above sits beside.

[All findings](../live-findings)
