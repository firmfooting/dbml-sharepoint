---
title: "access.role-binding.web-scope-by-group"
surface: access
scope: role-binding
question: web-scope-by-group
probe_surface: access
state: void
lanes: machine, visible
---

<!-- markdownlint-disable MD013 -->

# access.role-binding.web-scope-by-group

- Probe surface: access
- Run: reader-bindings/20260903-void-differential
- Question: Which groups hold a WEB-scope role assignment, and what?

## machine

- Outcome: `NOT ESTABLISHED (HTTP 403)`
- Evidence: could not enumerate web role assignments

## visible

- Question: web-scope role assignments readable by this identity
- Verdict: `confirmed`
- Confidence: 0.97
- Expected: owner: enumerable
- Expected: second-reader: refused
- Summary: Same check, two identities: the owner lane enumerates web-scope role assignments (settled PASS, run 20260903T050218Z); the second-reader lane is refused with HTTP 403 and the row records state=void, voided by the R4c readability control (CONTROL FAILED, METHOD VOID), run 20260903T050150Z. Both runs exit 0.

![access.role-binding.web-scope-by-group](/findings/access/reader-bindings/20260903-void-differential/web-scope-by-group.png)

[All findings](../live-findings)
