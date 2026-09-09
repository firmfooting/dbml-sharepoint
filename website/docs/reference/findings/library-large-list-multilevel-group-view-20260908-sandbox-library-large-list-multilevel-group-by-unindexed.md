---
title: "library.large-list.multilevel-group-by-unindexed"
surface: library
scope: large-list
question: multilevel-group-by-unindexed
probe_surface: library
state: void
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# library.large-list.multilevel-group-by-unindexed

- Probe surface: library
- Run: library-large-list-multilevel-group-view/20260908-sandbox
- Question: Is a three-level group-by on LVChoice, LVNumber, LVDate honoured, ignored or refused while all three are unindexed

## machine

- Outcome: `VOID`
- Evidence: the narrowed control did not hold, so a refusal here cannot be told from the server rejecting a three-FieldRef \<GroupBy>. What was observed anyway: collapsed HTTP 500 returned 0 row(s) against a RowLimit of 100, labels \{"LVChoice":\[],"LVNumber":\[],"LVDate":\[]}, grouping markers \[], dimensions honoured 0 of 3 on the collapsed rows (\[]) and 0 of 3 on the expanded rows (\[]), first row null; expanded HTTP 500 returned 0 row(s); the same query with no \<GroupBy> returned HTTP 200 with 100 row(s); ViewXml \<View>\<Query>\<GroupBy Collapse="TRUE">\<FieldRef Name="LVChoice"/>\<FieldRef Name="LVNumber"/>\<FieldRef Name="LVDate"/>\</GroupBy>\</Query>\<ViewFields>\<FieldRef Name="FileLeafRef"/>\<FieldRef Name="LVChoice"/>\<FieldRef Name="LVNumber"/>\<FieldRef Name="LVDate"/>\</ViewFields>\<RowLimit>100\</RowLimit>\</View>; collapsed body \{"odata.error":\{"code":"-2147467259, Microsoft.SharePoint.SPException","message":\{"lang":"en-US","value":"Cannot complete this action.\\n\\nPlease try again."}}}

[All findings](../live-findings)
