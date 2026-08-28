---
title: "chain-40-editor"
---

<!-- markdownlint-disable MD013 -->

# chain-40-editor (visible)

- Package: caml-chain-depth-visible-findings
- Question: does the Chain 40 filter editor show the stored 40 conditions or refuse?
- Verdict: `contradicted`
- Confidence: 0.97
- Expected: 40 editable conditions, or a complex-filter refusal
- Summary: The Chain 40 editor shows neither the forty stored conditions nor a refusal: it renders ten condition rows. This re-confirms the prior run's U2 finding (ten conditions of forty, saving truncates to ten). The guard is what converts this silent truncation into a refusal: the bare Chain 40 truncates, while the guarded shapes T2 and W4 refuse.
- Observation: The filter editor renders editable condition rows rather than a complex-filter refusal
- Observation: The structured text shows ten condition rows, not the forty stored disjuncts
- Observation: The accessibility snapshot has no complex-filter refusal text

![chain-40-editor](/findings/caml-chain-depth-visible-findings/chain-40-editor.png)

[All findings](../live-findings)
