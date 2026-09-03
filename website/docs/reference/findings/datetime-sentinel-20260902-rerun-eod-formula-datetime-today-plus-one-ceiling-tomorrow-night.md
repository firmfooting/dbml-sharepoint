---
title: "formula.datetime.today-plus-one-ceiling-tomorrow-night"
surface: formula
scope: datetime
question: today-plus-one-ceiling-tomorrow-night
probe_surface: formula
state: open
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# formula.datetime.today-plus-one-ceiling-tomorrow-night

- Probe surface: formula
- Run: datetime-sentinel/20260902-rerun-eod
- Question: Under \<= TODAY()+1, the exact ceiling (tomorrow 23:00)

## machine

- Outcome: `NOT ESTABLISHED`
- Evidence: 2026-09-04T13:00:00.000Z is 23:00 tomorrow in THIS browser's zone, and the site offset TZ0 determined does not put it exactly one site-local day ahead. Either answer would be about a day this run cannot name, so neither is recorded. Re-run from a machine in the site zone.

[All findings](../live-findings)
