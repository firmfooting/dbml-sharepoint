---
title: "access.list-acl.control-unknown-principal-refused"
surface: access
scope: list-acl
question: control-unknown-principal-refused
probe_surface: access
state: failed
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# access.list-acl.control-unknown-principal-refused

- Probe surface: access
- Run: operator-safety-grant/20261016-0627527a
- Question: NEGATIVE CONTROL: removeroleassignment naming a principal and a level that do not exist is refused on the broken scope

## machine

- Outcome: `FAIL`
- Evidence: removeroleassignment accepted a nonexistent principal and level with HTTP 200, so a 200 from the real removal below is not evidence of anything.

[All findings](../live-findings)
