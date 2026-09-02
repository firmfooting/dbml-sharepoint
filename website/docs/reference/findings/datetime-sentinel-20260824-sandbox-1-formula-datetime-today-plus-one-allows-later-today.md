---
title: "formula.datetime.today-plus-one-allows-later-today"
surface: formula
scope: datetime
question: today-plus-one-allows-later-today
probe_surface: formula
state: open
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# formula.datetime.today-plus-one-allows-later-today

- Probe surface: formula
- Run: datetime-sentinel/20260824-sandbox-1
- Question: Under \<= TODAY()+1, an item stamped LATER TODAY saves

## machine

- Recorded as: `V4`
- Outcome: `NOT ESTABLISHED`
- Evidence: time-of-day gate closed (see TZ0)

[All findings](../live-findings)
