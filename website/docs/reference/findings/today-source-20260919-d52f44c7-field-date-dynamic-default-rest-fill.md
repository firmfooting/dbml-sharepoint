---
title: "field.date.dynamic-default-rest-fill"
surface: field
scope: date
question: dynamic-default-rest-fill
probe_surface: formula
state: open
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# field.date.dynamic-default-rest-fill

- Probe surface: formula
- Run: today-source/20260919-d52f44c7
- Question: a \[today] dynamic default filled through REST

## machine

- Outcome: `NOT REACHED`
- Evidence: ADD\_DEFAULT\_COLUMN is off, so TD was never created and the question was not asked. Set ADD\_DEFAULT\_COLUMN and ALLOW\_WRITES and run again.

[All findings](../live-findings)
