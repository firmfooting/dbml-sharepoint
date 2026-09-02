---
title: "formula.datetime.today-rejects-earlier-today"
surface: formula
scope: datetime
question: today-rejects-earlier-today
probe_surface: formula
state: open
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# formula.datetime.today-rejects-earlier-today

- Probe surface: formula
- Run: datetime-sentinel/20260824-sandbox-1
- Question: Under \<= TODAY(), an item stamped EARLIER TODAY is rejected

## machine

- Recorded as: `V3`
- Outcome: `NOT ESTABLISHED`
- Evidence: time-of-day gate closed (see TZ0)

[All findings](../live-findings)
