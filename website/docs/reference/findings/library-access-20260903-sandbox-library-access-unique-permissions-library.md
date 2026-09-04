---
title: "library.access.unique-permissions-library"
surface: library
scope: access
question: unique-permissions-library
probe_surface: library
state: open
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# library.access.unique-permissions-library

- Probe surface: library
- Run: library-access/20260903-sandbox
- Question: Can a document library break role inheritance and hold unique permissions over REST, the way a list can

## machine

- Outcome: `NOT ESTABLISHED`
- Evidence: after the break the library read HasUniqueRoleAssignments=false (HTTP 200)

[All findings](../live-findings)
