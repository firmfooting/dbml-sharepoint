---
title: "Q5"
---

<!-- markdownlint-disable MD013 -->

# Q5 (machine)

- Package: view-aggregations-totals
- Question: Aggregations binds by INTERNAL name, not display title
- Outcome: `MANUAL`
- Evidence: wrote Name="SecondAmount" while its DISPLAY title is "Second Amount Display"; readback "\<FieldRef Name=\\"Amount\\" Type=\\"SUM\\" />\<FieldRef Name=\\"SecondAmount\\" Type=\\"AVG\\" />" with status On and seeds 1,3. OPEN THE VIEW: a figure under "Second Amount Display" means INTERNAL names bind (what the tool assumes). No figure under it means DISPLAY titles bind, and every shipped totals view is silently empty.

[All findings](../live-findings)
