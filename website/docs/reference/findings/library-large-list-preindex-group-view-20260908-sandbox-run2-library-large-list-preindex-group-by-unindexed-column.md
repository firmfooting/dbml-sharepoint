---
title: "library.large-list.preindex-group-by-unindexed-column"
surface: library
scope: large-list
question: preindex-group-by-unindexed-column
probe_surface: library
state: void
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# library.large-list.preindex-group-by-unindexed-column

- Probe surface: library
- Run: library-large-list-preindex-group-view/20260908-sandbox-run2
- Question: Is a group-by on the unindexed PNumber honoured, ignored or refused on this library at this size
- Voided by: library.large-list.control-missing-group-column-ungrouped, library.large-list.control-preindex-group-by-narrowed-honoured

## machine

- Outcome: `REFUSED (threshold)`
- Evidence: with PNumber: Indexed=false, AutoIndexed=false over 5100 file(s), where PNumber holds the file number modulo 1000 and therefore about 1000 distinct values: collapsed HTTP 500 returned 0 row(s) against a RowLimit of 100, labels \{"PNumber":\[]}, grouping markers \[], first row null; expanded HTTP 500 returned 0 row(s); the same query with no \<GroupBy> returned HTTP 200 with 100 row(s); ViewXml \<View>\<Query>\<GroupBy Collapse="TRUE">\<FieldRef Name="PNumber"/>\</GroupBy>\</Query>\<ViewFields>\<FieldRef Name="FileLeafRef"/>\<FieldRef Name="PNumber"/>\</ViewFields>\<RowLimit>100\</RowLimit>\</View>; collapsed body \{"odata.error":\{"code":"-2147024860, Microsoft.SharePoint.SPQueryThrottledException","message":\{"lang":"en-US","value":"The attempted operation is prohibited because it exceeds the list view threshold."}}}. The throttle is in force on the grouped surface of this library, which is what makes the crux row above a comparison rather than a reading of a library that is not enforcing anything.

[All findings](../live-findings)
