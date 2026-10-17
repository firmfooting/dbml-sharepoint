---
title: "view.threshold-render.unindexed-filter"
surface: view
scope: threshold-render
question: unindexed-filter
probe_surface: scale
state: open
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# view.threshold-render.unindexed-filter

- Probe surface: scale
- Run: threshold-index/20261017-6bdd7e60
- Question: RENDERED view, UNINDEXED filter, unguarded (manual: look)

## machine

- Outcome: `MANUAL (unobserved)`
- Evidence: \[6000 item(s), run 'join-created-modified'] OPEN \<sharepoint-url> Probe Threshold/Threshold VWUNI.aspx and report ONE of: "rows" (it listed items) or "threshold" (it showed the list view threshold message). Until somebody looks, this question is open. The filter is \<Where>\<Eq>\<FieldRef Name='Shadow'/>\<Value Type='Text'>Z\</Value>\</Eq>\</Where>

[All findings](../live-findings)
