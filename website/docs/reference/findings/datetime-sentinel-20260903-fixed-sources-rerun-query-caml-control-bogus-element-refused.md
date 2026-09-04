---
title: "query.caml.control-bogus-element-refused"
surface: query
scope: caml
question: control-bogus-element-refused
probe_surface: formula
state: failed
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# query.caml.control-bogus-element-refused

- Probe surface: formula
- Run: datetime-sentinel/20260903-fixed-sources-rerun
- Question: NEGATIVE CONTROL: CAML containing a bogus \<Nowww/> is refused

## machine

- Outcome: `FAIL`
- Evidence: unknown element accepted (no validation); \<Now/>=0 rows vs \<Nowww/>=0 rows, the SAME count, so the element name is not being interpreted and C1-C5 prove nothing about \<Now/> being real

[All findings](../live-findings)
