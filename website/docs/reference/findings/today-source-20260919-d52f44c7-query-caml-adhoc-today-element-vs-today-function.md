---
title: "query.caml-adhoc.today-element-vs-today-function"
surface: query
scope: caml-adhoc
question: today-element-vs-today-function
probe_surface: formula
state: open
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# query.caml-adhoc.today-element-vs-today-function

- Probe surface: formula
- Run: today-source/20260919-d52f44c7
- Question: CAML T Eq \<Today/> matches the =TODAY()-filled rows

## machine

- Outcome: `NOT ESTABLISHED`
- Evidence: the 31 rows carrying T hold 2 different days (2026-09-02, 2026-09-19), so ALL-versus-NONE does not separate the clocks. Observed 6 row(s): #29 T=2026-09-19T00:00:00, #30 T=2026-09-19T00:00:00, #31 T=2026-09-19T00:00:00, #32 T=2026-09-19T00:00:00, #33 T=2026-09-19T00:00:00, #34 T=2026-09-19T00:00:00. fixture: 31 row(s), 31 carrying T on 2 distinct day(s), 6 carrying DM, 6 modified today (2026-09-19 local)

[All findings](../live-findings)
