---
title: "view-aggregations-totals"
probe_surface: view
state: needs-human
lanes: visible
---

<!-- markdownlint-disable MD013 -->

# view-aggregations-totals

- Probe surface: view
- Run: view-aggregations/20260827-totals
- Question: Does the Probe totals view render the two seed rows plus a totals row (Sum 42 under Amount, AVG 21 under Second Amount Display)?

## visible

- Verdict: `contradicted`
- Confidence: 0.95
- Expected: Both seed rows render, and a totals row shows Sum 42 under Amount and AVG 21 under Second Amount Display
- Summary: The totals row renders but the Sum aggregation is broken. 'Second Amount Display' shows 'Average= 2' (correct: AVG of 1 and 3), but 'Amount' shows 'Count= undefined' instead of 'Sum= 42'. Both seed rows render (probe 10 = Amount 10, probe 32 = Amount 32). The stored aggregation is \<FieldRef Name="Amount" Type="Sum" />\<FieldRef Name="SecondAmount" Type="AVG" /> (Q3 round-trips), so the mismatch is between stored Type='Sum' and rendered 'Count= undefined' - consistent with the aggregation Type value's case mattering to the classic view renderer ('AVG' uppercase renders, 'Sum' capitalised does not).
- Observation: Both seed rows render: 'probe 10' (Amount 10) and 'probe 32' (Amount 32)
- Observation: The 'Amount' totals cell shows 'Count= undefined', not 'Sum= 42'
- Observation: The 'Second Amount Display' totals cell shows 'Average= 2'

![view-aggregations-totals](/findings/view/view-aggregations/20260827-totals/view-aggregations-totals.png)

[All findings](../live-findings)
