---
title: "library.large-list.filtered-group-by-past-threshold"
surface: library
scope: large-list
question: filtered-group-by-past-threshold
probe_surface: library
state: void
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# library.large-list.filtered-group-by-past-threshold

- Probe surface: library
- Run: library-large-list-group-view/20260908-sandbox
- Question: Is a group-by on the unindexed LVChoice served once a \<Where> on Id has narrowed the rows
- Voided by: library.large-list.control-missing-group-column-ungrouped

## machine

- Outcome: `HONOURED OVER THE FILTERED ROWS`
- Evidence: \<Where>\<Geq> on ID at 5495 (the newest item id 5500 less 5), with LVChoice: Indexed=false, AutoIndexed=false. The counter spelling was tried rather than assumed: Type="Counter": HTTP 200, SERVED (6 row(s)), so Type="Counter" is what answered. The same filter with no \<GroupBy> returned 6 row(s) naming \["dbmlsp-lv-05495.txt","dbmlsp-lv-05496.txt","dbmlsp-lv-05497.txt","dbmlsp-lv-05498.txt","dbmlsp-lv-05499.txt","dbmlsp-lv-05500.txt"], a count READ rather than predicted because item ids need not be contiguous. collapsed HTTP 200 returned 4 row(s) against a RowLimit of 100, labels \["Alpha","Beta","Delta","Gamma"], grouping markers \["LVChoice.COUNT.group","LVChoice.newgroup","LVChoice.groupindex"], first row \{"LVChoice":"Alpha","LVChoice.urlencoded":"%3B%23Alpha%3B%23","LVChoice.singleurlencoded":"Alpha","LVChoice.COUNT.group":"2","LVChoice.newgroup":"1","LVChoice.groupindex":"1\_","PreviewThumbnailsQualitySets":""}; expanded HTTP 200 returned 6 row(s); the same query with no \<GroupBy> returned HTTP 200 with 6 row(s); ViewXml \<View>\<Query>\<Where>\<Geq>\<FieldRef Name="ID"/>\<Value Type="Counter">5495\</Value>\</Geq>\</Where>\<GroupBy Collapse="TRUE">\<FieldRef Name="LVChoice"/>\</GroupBy>\</Query>\<ViewFields>\<FieldRef Name="FileLeafRef"/>\<FieldRef Name="LVNumber"/>\<FieldRef Name="LVChoice"/>\</ViewFields>\<RowLimit>100\</RowLimit>\</V. The values those filtered rows hold, off the expanded query, are \["Alpha","Beta","Delta","Gamma"] and the collapsed labels are \["Alpha","Beta","Delta","Gamma"]. The group was built over the rows the filter kept, so a filtered view groups what it shows. Read this beside library.view.filter-with-group-by, which measured the same composition on a library of six files.

[All findings](../live-findings)
