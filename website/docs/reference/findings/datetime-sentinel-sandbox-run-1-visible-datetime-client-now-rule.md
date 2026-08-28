---
title: "datetime-client-now-rule"
---

<!-- markdownlint-disable MD013 -->

# datetime-client-now-rule (visible)

- Package: datetime-sentinel-sandbox-run-1
- Question: Does the stored @now ClientValidationFormula actually control ProbeWhen visibility in the list form?
- Verdict: `needs_human`
- Confidence: 0.99
- Expected: The form loads without an error surface
- Expected: ProbeWhen visibility is observed under a state where the @now rule should be true and under a state where it should be false
- Expected: The two controlled states discriminate rather than merely showing that the formula was stored
- Summary: The New item form loads and ProbeWhen is hidden while Title, ProbeQuote and Attachments are visible. This is only the blank new-item state. It does not establish that the @now formula discriminates correctly between a past and future ProbeWhen value.
- Observation: The New item form loads without an error surface.
- Observation: ProbeWhen is not visible or accessible in the blank New item form, while Title, ProbeQuote and Attachments are present.
- Observation: No captured state contains a populated past or future ProbeWhen value, so the evidence cannot prove the rule changes visibility rather than hiding the field unconditionally.

![datetime-client-now-rule](/findings/datetime-sentinel-sandbox-run-1/datetime-client-now-rule.png)

[All findings](../live-findings)
