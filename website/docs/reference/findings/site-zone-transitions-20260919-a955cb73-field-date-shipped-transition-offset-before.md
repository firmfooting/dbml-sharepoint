---
title: "field.date.shipped-transition-offset-before"
surface: field
scope: date
question: shipped-transition-offset-before
probe_surface: field
state: failed
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# field.date.shipped-transition-offset-before

- Probe surface: field
- Run: site-zone-transitions/20260919-a955cb73
- Question: SharePoint's offset one minute before each sampled America/New\_York transition

## machine

- Outcome: `FAIL`
- Evidence: 2025-11-02T06:00:00Z -1 min: SharePoint -420, table -240, browser Intl -240 | 2026-03-08T07:00:00Z -1 min: SharePoint -480, table -300, browser Intl -300 | 2026-11-01T06:00:00Z -1 min: SharePoint -420, table -240, browser Intl -240

[All findings](../live-findings)
