---
title: "formula.datetime.client-now-rule"
surface: formula
scope: datetime
question: client-now-rule
probe_surface: formula
state: needs-human
lanes: visible
---

<!-- markdownlint-disable MD013 -->

# formula.datetime.client-now-rule

- Probe surface: formula
- Run: datetime-sentinel/20260824-sandbox-1
- Question: Does the stored current-time ClientValidationFormula control ProbeWhen visibility across both past and future item states?

## visible

- Recorded as: `datetime-client-now-rule-v2`
- Verdict: `needs_human`
- Confidence: 0.99
- Expected: The form loads without an error surface
- Expected: ProbeWhen visibility is observed in both a past and a future controlled state
- Expected: The two states discriminate rather than merely showing that the formula was stored
- Summary: The blank New item form rendered normally. Title, ProbeQuote and Attachments were visible, while ProbeWhen was not visible. One blank New item state cannot establish both past and future branches of the conditional visibility rule.
- Observation: The screenshot shows Title, ProbeQuote and Attachments, with no visible ProbeWhen field or error surface.
- Observation: Accessibility and structured visible content identify the exact New item page and likewise contain Title, ProbeQuote and Attachments without ProbeWhen.
- Supersedes: datetime-client-now-rule, captured 20260824T112739.358718Z — re-captured with a two-state discriminator; the 11:27 capture shows only that the formula was stored

![formula.datetime.client-now-rule](/findings/formula/datetime-sentinel/20260824-sandbox-1/datetime-client-now-rule-v2.png)

[All findings](../live-findings)
