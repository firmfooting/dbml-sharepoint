---
title: "datetime-client-now-rule-v2"
---

<!-- markdownlint-disable MD013 -->

# datetime-client-now-rule-v2 (visible)

- Package: datetime-client-now-rule
- Question: Does the stored current-time ClientValidationFormula control ProbeWhen visibility across both past and future item states?
- Verdict: `needs_human`
- Confidence: 0.99
- Expected: The form loads without an error surface
- Expected: ProbeWhen visibility is observed in both a past and a future controlled state
- Expected: The two states discriminate rather than merely showing that the formula was stored
- Summary: The blank New item form rendered normally. Title, ProbeQuote and Attachments were visible, while ProbeWhen was not visible. One blank New item state cannot establish both past and future branches of the conditional visibility rule.
- Observation: The screenshot shows Title, ProbeQuote and Attachments, with no visible ProbeWhen field or error surface.
- Observation: Accessibility and structured visible content identify the exact New item page and likewise contain Title, ProbeQuote and Attachments without ProbeWhen.

![datetime-client-now-rule-v2](/findings/datetime-client-now-rule/datetime-client-now-rule-v2.png)

[All findings](../live-findings)
