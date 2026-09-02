---
title: "query.view-query.today-include-time-roundtrip"
surface: query
scope: view-query
question: today-include-time-roundtrip
probe_surface: formula
state: open
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# query.view-query.today-include-time-roundtrip

- Probe surface: formula
- Run: datetime-sentinel/20260902-tz-gate-closed
- Question: A saved view using \<Today/> + IncludeTimeValue keeps its query

## machine

- Outcome: `NOT ESTABLISHED`
- Evidence: time-of-day gate closed (see TZ0)

[All findings](../live-findings)
