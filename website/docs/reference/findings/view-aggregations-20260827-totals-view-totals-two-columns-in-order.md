---
title: "view.totals.two-columns-in-order"
surface: view
scope: totals
question: two-columns-in-order
probe_surface: view
state: open
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# view.totals.two-columns-in-order

- Probe surface: view
- Run: view-aggregations/20260827-totals
- Question: two totalled columns both render, in declaration order

## machine

- Recorded as: `Q6`
- Outcome: `MANUAL`
- Evidence: the same view now declares two aggregations; confirm BOTH figures appear, and that the readback above preserved declaration order. The deployer compares the string exactly, so a reordered readback would drift on every redeploy

[All findings](../live-findings)
