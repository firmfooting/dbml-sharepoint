---
title: "Q6"
---

<!-- markdownlint-disable MD013 -->

# Q6 (machine)

- Package: view-aggregations-totals
- Question: two totalled columns both render, in declaration order
- Outcome: `MANUAL`
- Evidence: the same view now declares two aggregations; confirm BOTH figures appear, and that the readback above preserved declaration order. The deployer compares the string exactly, so a reordered readback would drift on every redeploy

[All findings](../live-findings)
