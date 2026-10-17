---
title: "view.threshold-render.indexed-filter-guarded"
surface: view
scope: threshold-render
question: indexed-filter-guarded
probe_surface: scale
state: open
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# view.threshold-render.indexed-filter-guarded

- Probe surface: scale
- Run: threshold-index/20261017-6bdd7e60
- Question: RENDERED view, INDEXED filter, GUARDED (manual: look)

## machine

- Outcome: `MANUAL (unobserved)`
- Evidence: \[6000 item(s), run 'join-created-modified'] OPEN \<sharepoint-url> Probe Threshold/Threshold VWGRD.aspx and report ONE of: "rows" (it listed items) or "threshold" (it showed the list view threshold message). Until somebody looks, this question is open. The filter is \<Where>\<And>\<Eq>\<FieldRef Name='Bucket'/>\<Value Type='Text'>Z\</Value>\</Eq>\<Or>\<IsNotNull>\<FieldRef Name="ID"/>\</IsNotNull>\<IsNull>\<FieldRef Name="ID"/>\</IsNull>\</Or>\</And>\</Where>

[All findings](../live-findings)
