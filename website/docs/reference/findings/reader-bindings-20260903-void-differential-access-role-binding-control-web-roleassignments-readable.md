---
title: "access.role-binding.control-web-roleassignments-readable"
surface: access
scope: role-binding
question: control-web-roleassignments-readable
probe_surface: access
state: failed
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# access.role-binding.control-web-roleassignments-readable

- Probe surface: access
- Run: reader-bindings/20260903-void-differential
- Question: CONTROL: can this caller enumerate web/roleassignments at all?

## machine

- Outcome: `CONTROL FAILED, METHOD VOID (HTTP 403)`
- Evidence: this caller cannot enumerate web role assignments, so the census below cannot be taken by it

[All findings](../live-findings)
