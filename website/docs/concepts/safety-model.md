---
title: Safety model
sidebar_position: 3
---

# Safety model

The project's first rule: **when the script cannot prove an action is
what the declaration intends, it stops and names the reason.** Guessing
on someone's production site is the one unforgivable failure mode.

This page covers operational safeguards. For identity, credentials,
same-origin network reach and the governed-tenant review checklist, see the
[security model](security-model.md).

## Fail closed, everywhere

- The wrong site aborts before any request (site guard).
- A validation error at build time refuses to emit scripts at all.
- An existing list without this declaration's exact provenance marker fails
  before writes. Title, template, fields, row count and emptiness are not
  ownership authority.
- An existing object whose immutable shape differs from the declaration
  fails that object with a named error; nothing is mutated.
- A readback that does not match the write fails the phase.
- A drift the script cannot classify is reported, not "fixed".

## Write discipline

Every write follows the same shape: **read fresh → compute the narrow
delta → guard → write → read back → verify.** Whole-document writes
(such as view XML) additionally diff the readback against the exact
spliced document and refuse to proceed if anything else changed. A
merge that could destroy neighbouring settings is treated as hostile
until proven byte-safe.

## Protection features

The mapping can declare `seal_columns: true` (every deployed column's
schema is sealed against UI edits, even for admins; the deployer unseals
for its own maintenance runs and re-seals afterwards) and
`prevent_list_deletion: true` (`AllowDeletion` off). Rollback unlocks
these only per-list, only after deletion of that list is explicitly
authorised, and restores the lock if its delete fails. Protection is
never left stranded off.

## Retention and holds

Live-confirmed behaviour on retention-governed sites: retention blocks
deleting a list that still *contains* items, while an emptied list
deletes fine, and item recycling is always allowed (the policy keeps its
copies in the Preservation Hold Library). Rollback therefore recycles
items before deleting lists: `recycle()`, never a permanent delete, so
nothing it does is unrestorable. If an *empty* list is still refused, a
site-level hold applies; that is compliance enforcement the script will
never bypass. It names the situation and points at the compliance
admin.

## Undocumented surfaces

Some capabilities only exist on undocumented endpoints (view column
widths via `SetViewXml`, for example). The policy:

1. Reverse-engineer from what SharePoint's own UI sends, not from blog
   folklore.
2. Prove the mechanism live before productionising it.
3. Wrap it in the strictest guard in the codebase (read-splice-diff-
   write-verify), because undocumented means unwarranted.
4. Withdraw immediately when live behaviour disproves the surface: a
   feature that 400s on the wire is deleted, not retried harder.

## Honesty in output

If a step was skipped, the output says so. If a capability cannot be
assessed from the operator's context, the assessment prints it in a
not-assessable block instead of implying coverage. Error messages carry
the server's own reason. The transcript an operator pastes into a ticket
must be sufficient to diagnose the run.
