---
title: "library.large-list.control-multilevel-group-by-narrowed-honoured"
surface: library
scope: large-list
question: control-multilevel-group-by-narrowed-honoured
probe_surface: library
state: failed
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# library.large-list.control-multilevel-group-by-narrowed-honoured

- Probe surface: library
- Run: library-large-list-multilevel-group-view/20260908-sandbox
- Question: POSITIVE CONTROL: a three-level \<GroupBy> is honoured once a \<Where> on Id has narrowed the rows to a handful

## machine

- Outcome: `CONTROL FAILED, METHOD VOID`
- Evidence: \<Where>\<Geq> on ID at 5495 (the newest item id 5500 less 5), grouping on LVChoice then LVNumber then LVDate with all three unindexed. The counter spelling was tried rather than assumed: Type="Counter": HTTP 200, SERVED (6 row(s)), so Type="Counter" is what answered. collapsed HTTP 500 returned 0 row(s) against a RowLimit of 100, labels \{"LVChoice":\[],"LVNumber":\[],"LVDate":\[]}, grouping markers \[], dimensions honoured 0 of 3 on the collapsed rows (\[]) and 0 of 3 on the expanded rows (\[]), first row null; expanded HTTP 500 returned 0 row(s); the same query with no \<GroupBy> returned HTTP 200 with 6 row(s); ViewXml \<View>\<Query>\<Where>\<Geq>\<FieldRef Name="ID"/>\<Value Type="Counter">5495\</Value>\</Geq>\</Where>\<GroupBy Collapse="TRUE">\<FieldRef Name="LVChoice"/>\<FieldRef Name="LVNumber"/>\<FieldRef Name="LVDate"/>\</GroupBy>\</Query>\<ViewFields>\<FieldRef Name="FileLeafRef"/>\<FieldRef Name="LVChoice"/>\<FieldRef Name="LVNumber"/>\<FieldRe; collapsed body \{"odata.error":\{"code":"-2147467259, Microsoft.SharePoint.SPException","message":\{"lang":"en-US","value":"Cannot complete this action.\\n\\nPlease try again."}}}. The three-FieldRef shape was not honoured even over a handful of rows, so a refusal of the same shape at full size cannot be attributed to the threshold: it may be the shape. Read the collapsed body above before reading anything below it.

[All findings](../live-findings)
