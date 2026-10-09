---
title: "access.item-acl.break-copies-parent-groups"
surface: access
scope: item-acl
question: break-copies-parent-groups
probe_surface: access
state: open
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# access.item-acl.break-copies-parent-groups

- Probe surface: access
- Run: item-access/20261007-63d684c1
- Question: Does breakroleinheritance(copyRoleAssignments=true,clearSubscopes=true) on a file copy the library's group bindings, levels included?

## machine

- Outcome: `NOT REACHED`
- Evidence: STATE 1 asks this

[All findings](../live-findings)
