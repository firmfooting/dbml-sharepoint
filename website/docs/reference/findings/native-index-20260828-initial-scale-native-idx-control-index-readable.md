---
title: "scale.native-idx.control-index-readable"
surface: scale
scope: native-idx
question: control-index-readable
probe_surface: scale
state: failed
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# scale.native-idx.control-index-readable

- Probe surface: scale
- Run: native-index/20260828-initial
- Question: ID: does the Indexed property expose a platform-maintained index?

## machine

- Recorded as: `NATID`
- Outcome: `CONTROL FAILED, METHOD VOID`
- Evidence: 6 of 6 list(s) read: Indexed true on 0, false on 6, unreadable on 0; AutoIndexed true on 0, not exposed on 0. Indexed is false on ID, so either the property reports only author-added indexes or ID carries no index; this probe cannot distinguish those, and either way a property read cannot answer the four questions below. Use the behavioural test instead.

[All findings](../live-findings)
