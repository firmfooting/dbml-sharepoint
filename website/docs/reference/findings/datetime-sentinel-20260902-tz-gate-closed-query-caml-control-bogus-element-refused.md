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
- Run: datetime-sentinel/20260902-tz-gate-closed
- Question: NEGATIVE CONTROL: CAML containing a bogus \<Nowww/> is refused

## machine

- Outcome: `FAIL`
- Evidence: a query containing \<Nowww/> was ACCEPTED and returned 0 row(s). SharePoint is not validating this element, so C1-C5 prove nothing about \<Now/> being real

[All findings](../live-findings)
