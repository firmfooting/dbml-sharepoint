---
title: "access.built-in-level.masquerade-delete-guarded"
surface: access
scope: built-in-level
question: masquerade-delete-guarded
probe_surface: access
state: void
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# access.built-in-level.masquerade-delete-guarded

- Probe surface: access
- Run: built-in-levels/20260919-03432e71
- Question: Is DELETE refused for a custom level wearing a built-in RoleTypeKind?

## machine

- Outcome: `VOID`
- Evidence: the level read back with RoleTypeKind 0, so it is not wearing a built-in kind and cannot answer this

[All findings](../live-findings)
