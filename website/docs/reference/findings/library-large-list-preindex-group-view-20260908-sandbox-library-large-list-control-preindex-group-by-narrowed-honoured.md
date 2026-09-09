---
title: "library.large-list.control-preindex-group-by-narrowed-honoured"
surface: library
scope: large-list
question: control-preindex-group-by-narrowed-honoured
probe_surface: library
state: void
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# library.large-list.control-preindex-group-by-narrowed-honoured

- Probe surface: library
- Run: library-large-list-preindex-group-view/20260908-sandbox
- Question: POSITIVE CONTROL: a \<GroupBy> on PChoice is honoured once a \<Where> on Id has narrowed the rows to a handful
- Voided by: library.large-list.control-missing-group-column-ungrouped

## machine

- Outcome: `HONOURED`
- Evidence: \<Where>\<Geq> on ID at 5095 (the newest item id 5100 less 5), grouping on PChoice. The counter spelling was tried rather than assumed: Type="Counter": HTTP 200, SERVED (6 row(s)), so Type="Counter" is what answered. collapsed HTTP 200 returned 4 row(s) against a RowLimit of 100, labels \{"PChoice":\["Alpha","Beta","Delta","Gamma"]}, grouping markers \["PChoice.COUNT.group","PChoice.newgroup","PChoice.groupindex"], first row \{"PChoice":"Alpha","PChoice.urlencoded":"%3B%23Alpha%3B%23","PChoice.singleurlencoded":"Alpha","PChoice.COUNT.group":"2","PChoice.newgroup":"1","PChoice.groupindex":"1\_","PreviewThumbnailsQualitySets":""}; expanded HTTP 200 returned 6 row(s); the same query with no \<GroupBy> returned HTTP 200 with 6 row(s); ViewXml \<View>\<Query>\<Where>\<Geq>\<FieldRef Name="ID"/>\<Value Type="Counter">5095\</Value>\</Geq>\</Where>\<GroupBy Collapse="TRUE">\<FieldRef Name="PChoice"/>\</GroupBy>\</Query>\<ViewFields>\<FieldRef Name="FileLeafRef"/>\<FieldRef Name="PChoice"/>\</ViewFields>\<RowLimit>100\</RowLimit>\</View>. A \<GroupBy> on this column is therefore a request this server accepts and acts on, so a refusal of the same shape at full size below is about the size. #480 measured the same composition honoured on the other fixture; it is re-proved here because the column names and the build differ.

[All findings](../live-findings)
