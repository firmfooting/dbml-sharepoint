---
title: "field.lookup.showfield-display-name-spelling"
surface: field
scope: lookup
question: showfield-display-name-spelling
probe_surface: field
state: open
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# field.lookup.showfield-display-name-spelling

- Probe surface: field
- Run: lookup-showfield/20260920-41641bfa
- Question: NEGATIVE CONTROL: what does SharePoint do with a LookupField set to the target column's DISPLAY name rather than its internal name?

## machine

- Outcome: `NOT ESTABLISHED`
- Evidence: the display-name control is a separate armed pass and was not run. Take the eyes-on observation first, then set NEGATIVE\_DISPLAY\_NAME = true and paste again.

[All findings](../live-findings)
