---
title: "form.panel.edit-columns-writes-attributes"
surface: form
scope: panel
question: edit-columns-writes-attributes
probe_surface: form
state: open
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# form.panel.edit-columns-writes-attributes

- Probe surface: form
- Run: form-visibility/20260919-abf10e2c
- Question: the modern "Edit form columns" panel writes these attributes

## machine

- Outcome: `MANUAL: capture panel before/action, then recheck`
- Evidence: capture the Edit form columns panel before and immediately before save; after saving, re-run with RECHECK\_ONLY=true and capture the New, Edit and Display forms

[All findings](../live-findings)
