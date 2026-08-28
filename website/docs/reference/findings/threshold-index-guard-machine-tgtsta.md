---
title: "TGTSTA"
---

<!-- markdownlint-disable MD013 -->

# TGTSTA (machine)

- Package: threshold-index-guard
- Question: The INDEXED status filter on the lookup target
- Outcome: `NOT ESTABLISHED`
- Evidence: \[target holds 1] $filter=PickStatus eq 'Active', HTTP 200. Set SEED\_TARGET\_STATUS and re-paste: with nothing Active, PickCond is "" on every row and TGTCND / TGTFLT are about an empty column.

[All findings](../live-findings)
