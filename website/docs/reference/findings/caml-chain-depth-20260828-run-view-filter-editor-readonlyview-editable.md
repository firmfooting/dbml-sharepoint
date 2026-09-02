---
title: "view.filter-editor.readonlyview-editable"
surface: view
scope: filter-editor
question: readonlyview-editable
probe_surface: query
state: open
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# view.filter-editor.readonlyview-editable

- Probe surface: query
- Run: caml-chain-depth/20260828-run
- Question: if ReadOnlyView stuck, does the UI refuse to edit that view? (manual: look)

## machine

- Recorded as: `R3`
- Outcome: `NOT REACHED`
- Evidence: ReadOnlyView did not stick, so there is nothing to look at. R2 carries the answer.

[All findings](../live-findings)
