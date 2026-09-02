---
title: "view.filter-editor.ui-chain-40"
surface: view
scope: filter-editor
question: ui-chain-40
probe_surface: query
state: needs-human
lanes: machine, visible
---

<!-- markdownlint-disable MD013 -->

# view.filter-editor.ui-chain-40

- Probe surface: query
- Run: caml-chain-depth/20260828-run
- Question: the UI filter editor shows every condition, and re-saving does not truncate (manual: look)

## machine

- Recorded as: `U2`
- Outcome: `MANUAL`
- Evidence: On that same view, open the filter editor and COUNT the conditions it shows against the 40 that were stored. Then, WITHOUT changing anything, press Save, and re-paste this file with CLEANUP\_LIST empty to read the stored ViewQuery back. Report the \<Or> count before and after. A drop is the finding: it means the editor writes back only what it rendered, so opening a deployed view is enough to change what it means.

## visible

- Recorded as: `chain-40-editor`
- Question: does the Chain 40 filter editor show the stored 40 conditions or refuse?
- Verdict: `contradicted`
- Confidence: 0.97
- Expected: 40 editable conditions, or a complex-filter refusal
- Summary: The Chain 40 editor shows neither the forty stored conditions nor a refusal: it renders ten condition rows. This re-confirms the prior run's U2 finding (ten conditions of forty, saving truncates to ten). The guard is what converts this silent truncation into a refusal: the bare Chain 40 truncates, while the guarded shapes T2 and W4 refuse.
- Observation: The filter editor renders editable condition rows rather than a complex-filter refusal
- Observation: The structured text shows ten condition rows, not the forty stored disjuncts
- Observation: The accessibility snapshot has no complex-filter refusal text

![view.filter-editor.ui-chain-40](/findings/query/caml-chain-depth/20260828-run/chain-40-editor.png)

[All findings](../live-findings)
