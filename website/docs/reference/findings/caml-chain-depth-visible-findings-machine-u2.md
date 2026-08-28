---
title: "U2"
---

<!-- markdownlint-disable MD013 -->

# U2 (machine)

- Package: caml-chain-depth-visible-findings
- Question: the UI filter editor shows every condition, and re-saving does not truncate (manual: look)
- Outcome: `MANUAL`
- Evidence: On that same view, open the filter editor and COUNT the conditions it shows against the 40 that were stored. Then, WITHOUT changing anything, press Save, and re-paste this file with CLEANUP\_LIST empty to read the stored ViewQuery back. Report the \<Or> count before and after. A drop is the finding: it means the editor writes back only what it rendered, so opening a deployed view is enough to change what it means.

[All findings](../live-findings)
