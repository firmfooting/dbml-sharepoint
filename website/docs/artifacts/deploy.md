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
| PREPARE | site assessment · read-only preflight · permission levels and site groups · operator self-enrolment · enterprise reader enrolment · maintenance unseal |
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

After the paste, `verify.js.txt` exercises every clock cell the pack
relies on (date rules, view windows, `[today]` defaults) on one hidden
scratch list and prints a VERIFIED / MISMATCH / NOT-VERIFIED verdict; see
[verify.md](verify.md).

Each phase is fail-closed on its own: an error is tagged with its phase,
recorded in the summary, and never silently swallowed. Later phases
still run where they are independent, so one broken column does not hide
the state of everything else.

## What a rerun does

deploy.js.txt is a reconciler, not an installer:

- Objects that exist and verify are **skipped** (counted in the
  summary).
- An existing list is reconciled only when its Description already carries
  this declaration's exact provenance marker. A missing, foreign, copied or
  legacy marker blocks before writes; ordinary deploy never stamps ownership
  onto a title collision.
- Declared mutable settings that drifted are **narrowly reconciled** and
  read back.
- A list absent under its title but present under one of the entity's
  `renamed_from` titles, carrying the exact marker for that previous name,
  is **retitled in place** before anything else is written, and read back
  by list id. A previous title without its marker, or present beside the
  current title, blocks before writes.
- A permission level or site group absent under its name but present
  under one of its previous names (its `renamed_from` bases crossed with
  every `previous_prefixes` stem), carrying the exact marker for that
  previous name, is **renamed in place** at the start of the security
  phase, by id, and read back; assignments and members stay. Every rename
  is planned read-only first, and one refusal aborts before any is written.
- Objects whose immutable shape mismatches **fail closed** with a named
  error: the script never migrates types or retargets lookups.
- User content (undeclared views, rows, user-added columns) is never
  touched; `reconcile: exact` ACL mode is the single declared exception.

### First redeploy after this ownership gate

An older development build may have created lists before the current exact
family/entity marker existed. The first redeploy now blocks those lists rather
than silently stamping them.

Verify ownership from independent deployment evidence before editing a live
Description. If this tool created the list, preserve any human prose you need
and append or restore the exact marker printed by `assess.js.txt` and
`deploy-manifest.md`. If ownership cannot be proved, do not add the marker;
change the declaration's prefix/title or use an approved explicit migration.
Matching shape, an empty list or a familiar title is not proof of ownership.

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
