---
title: "view.filter-editor.mixed-group-right-editable"
surface: view
scope: filter-editor
question: mixed-group-right-editable
probe_surface: query
state: open
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# view.filter-editor.mixed-group-right-editable

- Probe surface: query
- Run: caml-chain-depth/20260828-run
- Question: EDITABILITY: And\[Eq, Or\[Eq,Eq]], MIXED with no IsNull (manual: look)

## machine

- Recorded as: `E3`
- Outcome: `MANUAL`
- Evidence: OPEN \<sharepoint-url> Probe Chain clfpjo/Shape E3.aspx, then its view settings, and report ONE of: "filter pane" (editable, so truncatable) or "complex filter" (refused, so protected). The query is 209 chars.

[All findings](../live-findings)
