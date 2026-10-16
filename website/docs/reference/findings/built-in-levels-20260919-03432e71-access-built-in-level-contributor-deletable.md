---
title: "access.built-in-level.contributor-deletable"
surface: access
scope: built-in-level
question: contributor-deletable
probe_surface: access
state: open
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# access.built-in-level.contributor-deletable

- Probe surface: access
- Run: built-in-levels/20260919-03432e71
- Question: Is DELETE refused on the built-in Contribute?

## machine

- Outcome: `NOT ESTABLISHED`
- Evidence: ALLOW\_DESTRUCTIVE\_DELETE is false. Microsoft documents four of the six roster levels as deletable, so this arm is a request to delete a built-in permission level, not a refusal-capture experiment. Set it only on a disposable site.

[All findings](../live-findings)
