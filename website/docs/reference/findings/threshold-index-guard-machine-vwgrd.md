---
title: "VWGRD"
---

<!-- markdownlint-disable MD013 -->

# VWGRD (machine)

- Package: threshold-index-guard
- Question: RENDERED view, INDEXED filter, GUARDED (manual: look)
- Outcome: `MANUAL (unobserved)`
- Evidence: \[6000 item(s)] OPEN \<sharepoint-url> Probe Threshold/Threshold VWGRD.aspx and report ONE of: "rows" (it listed items) or "threshold" (it showed the list view threshold message). Until somebody looks, this question is open. The filter is \<Where>\<And>\<Eq>\<FieldRef Name='Bucket'/>\<Value Type='Text'>Z\</Value>\</Eq>\<Or>\<IsNotNull>\<FieldRef Name="ID"/>\</IsNotNull>\<IsNull>\<FieldRef Name="ID"/>\</IsNull>\</Or>\</And>\</Where>

[All findings](../live-findings)
