---
title: Execution model
sidebar_position: 2
---

# Execution model

Every generated script is a single self-contained async IIFE pasted into
the browser console of the target site. That choice drives everything
else.

## Why the browser console

The operator's own session is the credential. There are no stored
secrets, no app principals, no consent grants, and therefore nothing to
rotate, leak or clean up. The cost is that an interactive operator must
be present; that is accepted deliberately (it is not unattended CI).

## The site guard

Pasting a deployment script into the wrong site must be impossible to
get wrong silently. Every script starts by comparing
`window.location` and `_spPageContextInfo` against the site URL baked in
at build time (origin and server-relative path both) and aborts before
any request if they differ. It then logs the operator identity
("Running as ...") so the console transcript records who ran what.

## HTTP transport

All REST traffic rides a shared transport
([`_http.js.j2`](../api/templates.md)):

- **Throttle-aware.** SharePoint Online throttles bursts (HTTP 429) and
  sheds load (503). Every request honours `Retry-After`, else backs off
  exponentially, before surfacing the final response to the caller's own
  error handling.
- **Instrumented.** A `DEBUG` flag (default `false`, editable in the
  pasted script, no rebuild) prints per-request timing lines and, for
  deploy.js.txt, a per-phase seconds table before `DONE`. The `DONE` line
  always carries elapsed seconds and total request count.
- **Read-safe by construction.** The transport partial contains no write
  helper; write headers live in a separate partial included only by the
  scripts that write. The read-only assessment script can therefore be
  audited as read-only from its text alone.

Request digests come from a cached `getDigest()` that refreshes 60
seconds before `FormDigestTimeoutSeconds` expiry: per-call safety at
roughly one `contextinfo` POST per run.

## Phases and lanes

deploy.js.txt runs the phase sequence from the
[phases manifest](architecture.md#the-phases-manifest): PREPARE
(preflight, security principals, enrolment, maintenance unseal),
STRUCTURE (lists, deferred lookups, indexes, defaults), PRESENTATION
(views, forms), PROTECTION (seal, ACLs), DATA (seeds).

Within a phase, parallelism follows the **lane rule**: SharePoint stores
fields and views in the list schema, and concurrent schema writes to the
*same* list race into save conflicts, but different lists are fully
independent. So the unit of parallelism is the list: work is grouped
into lanes by list, items within a lane run strictly sequentially, lanes
run concurrently (bounded). Never parallelise same-list schema writes.

## Idempotence and reconciliation

Rerunning any script must be safe:

- **Existing objects are adopted, never assumed.** A list that already exists
  must carry this declaration's exact provenance marker, and its immutable
  shape must match. Existing fields must match their immutable shape. Any
  mismatch fails that object closed with a named error. Explicit migration
  beats silent mutation. The immutable
  set is: internal name, `TypeAsString`, `ReadOnlyField`, unexpected
  sealing, the lookup's target list and target field, and the list's base
  template.
- **Mutable settings are reconciled narrowly.** Only drifted declared
  settings are sent (narrow MERGE), and every write is read back and
  compared before the phase reports success. A calculated column's
  `Formula` is **in this group, not the immutable one**. Drift is
  overwritten with the declaration rather than failing the object closed.
  So is a Choice column's `Choices`. Both then fail the phase if the write
  does not stick, with the declared and read-back values named in the
  error, but the intended outcome is convergence on the mapping, not
  refusal.
- **Content is never touched.** Undeclared views, user rows and user
  columns are user content; deploy.js.txt reconciles only what the mapping
  declares (the one exception is `reconcile: exact` ACL mode, which the
  mapping must opt into).

## Operator-facing output

The console transcript is the run record, so its readability is a
feature. Live finding, generalised: probes whose "absent" answer is a
404 or 400 paint red in the console and operators read them as failures,
so existence checks ride always-200 enumerations instead of per-item
probes wherever possible, and errors carry SharePoint's own
`error.message.value` rather than a bare status code.
