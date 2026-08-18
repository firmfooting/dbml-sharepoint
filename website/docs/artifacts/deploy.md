---
title: deploy.js.txt
sidebar_position: 1
---

# deploy.js.txt

The deployment script. Paste the whole file into the target site's
browser console; wait for the `[SP-DEPLOY] [DONE]` line and a summary
ending `errors: []`.

## Phases

Phase numbers derive from the phases manifest and renumber automatically
when the structure changes; the groups are stable:

| Group | Steps |
| --- | --- |
| PREPARE | site assessment · read-only preflight · permission levels and site groups · operator self-enrolment · maintenance unseal |
| STRUCTURE | list creation · deferred lookups · indexed columns · field defaults |
| PRESENTATION | views · form formatting |
| PROTECTION | seal declared columns · role inheritance and assignments |
| DATA | seed items (extension-provided) |

The first phase, at the top of PREPARE, runs the same site assessment as
`assess.js.txt` (see [assess.md](assess.md) for what it checks). A
**BLOCKED** verdict aborts with `assessment-blocked` and cannot be
overridden. A **DEGRADED** verdict aborts with
`assessment-degraded-unacknowledged` unless the operator sets
`const ACKNOWLEDGE_DEGRADED = true;` near the top of the script and pastes
it again. `assess.js.txt` still ships unchanged alongside `deploy.js.txt`,
so it can still be handed to somebody whose tenant you do not own, to
check compatibility without provisioning anything.

Each phase is fail-closed on its own: an error is tagged with its phase,
recorded in the summary, and never silently swallowed. Later phases
still run where they are independent, so one broken column does not hide
the state of everything else.

## What a rerun does

deploy.js.txt is a reconciler, not an installer:

- Objects that exist and verify are **skipped** (counted in the
  summary).
- Declared mutable settings that drifted are **narrowly reconciled** and
  read back.
- Objects whose immutable shape mismatches **fail closed** with a named
  error: the script never migrates types or retargets lookups.
- User content (undeclared views, rows, user-added columns) is never
  touched; `reconcile: exact` ACL mode is the single declared exception.

## Views

Declared views reconcile like fields: created with a clean URL (the
`.aspx` name is fixed at creation, so views are created under a
URL slug and renamed to the declared title), fields asserted in order,
CAML query, row limit, grouping, formatting and per-column widths
verified by readback. Existing escaped-URL views migrate to the clean
URL once, transferring default-view status before the old page is
deleted.

## DEBUG mode

Edit `const DEBUG = false` to `true` at the top of the pasted script (no
rebuild needed) for per-request timing lines and a per-phase seconds
table before `DONE`. The `DONE` line always reports elapsed seconds and
request count, DEBUG or not.

## Requirements

Run from `.../_layouts/15/settings.aspx` (a classic page, the
wrong-site guard needs `_spPageContextInfo`), signed in as a Site Owner.
The preflight verifies the effective permission bits it needs and aborts
with a named finding if they are missing.
