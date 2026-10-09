---
title: "access.item-acl.control-test-user-denied"
surface: access
scope: item-acl
question: control-test-user-denied
probe_surface: access
state: open
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# access.item-acl.control-test-user-denied

- Probe surface: access
- Run: item-access/20261007-63d684c1
- Question: CONTROL: before any grant, the test user's effective permissions on the C3 file carry no ViewListItems

## machine

- Outcome: `NOT REACHED`
- Evidence: STATE 1 asks this

[All findings](../live-findings)
