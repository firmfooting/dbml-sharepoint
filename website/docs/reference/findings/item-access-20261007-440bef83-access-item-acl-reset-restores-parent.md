---
title: "access.item-acl.reset-restores-parent"
surface: access
scope: item-acl
question: reset-restores-parent
probe_surface: access
state: open
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# access.item-acl.reset-restores-parent

- Probe surface: access
- Run: item-access/20261007-440bef83
- Question: Does resetroleinheritance on a broken file restore exactly the library's bindings and drop its direct user grant?

## machine

- Outcome: `NOT REACHED`
- Evidence: STATE 2 asks this, on what STATE 1 leaves

[All findings](../live-findings)
