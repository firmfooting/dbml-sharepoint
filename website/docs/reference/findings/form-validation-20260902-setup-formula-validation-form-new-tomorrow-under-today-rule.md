---
title: "formula.validation.form-new-tomorrow-under-today-rule"
surface: formula
scope: validation
question: form-new-tomorrow-under-today-rule
probe_surface: formula
state: open
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# formula.validation.form-new-tomorrow-under-today-rule

- Probe surface: formula
- Run: form-validation/20260902-setup
- Question: form: New with DT = tomorrow shows the DT message

## machine

- Outcome: `MANUAL`
- Evidence: New, Title "form-2", DT = tomorrow, Save; note what happened, then run again with MODE = 'report'

[All findings](../live-findings)
