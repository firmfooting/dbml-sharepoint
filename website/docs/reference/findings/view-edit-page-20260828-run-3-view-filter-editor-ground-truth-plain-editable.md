---
title: "view.filter-editor.ground-truth-plain-editable"
surface: view
scope: filter-editor
question: ground-truth-plain-editable
probe_surface: view
state: open
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# view.filter-editor.ground-truth-plain-editable

- Probe surface: view
- Run: view-edit-page/20260828-run-3
- Question: GROUND TRUTH: does the plain view open its filter pane? (manual: look)

## machine

- Recorded as: `P1`
- Outcome: `MANUAL`
- Evidence: OPEN \<sharepoint-url> Probe ViewEdit cjmg37/Plain.aspx, then its view settings, and report ONE of: "filter pane" (editable) or "complex filter" (refused). This is expected to be editable, and if it is not then the comparison has no editable side and every row above is measuring two refused pages.

[All findings](../live-findings)
