---
title: "view.totals.binds-by-internal-name"
surface: view
scope: totals
question: binds-by-internal-name
probe_surface: view
state: open
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# view.totals.binds-by-internal-name

- Probe surface: view
- Run: view-aggregations/20260827-totals
- Question: Aggregations binds by INTERNAL name, not display title

## machine

- Recorded as: `Q5`
- Outcome: `MANUAL`
- Evidence: wrote Name="SecondAmount" while its DISPLAY title is "Second Amount Display"; readback "\<FieldRef Name=\\"Amount\\" Type=\\"SUM\\" />\<FieldRef Name=\\"SecondAmount\\" Type=\\"AVG\\" />" with status On and seeds 1,3. OPEN THE VIEW: a figure under "Second Amount Display" means INTERNAL names bind (what the tool assumes). No figure under it means DISPLAY titles bind, and every shipped totals view is silently empty.

[All findings](../live-findings)
