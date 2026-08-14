---
title: rollback.js.txt
sidebar_position: 2
---

# rollback.js.txt

Deletes the lists this schema declared at this site, the escape hatch
for a failed first provision and the teardown half of
deploy–demonstrate–delete. It is deliberately harder to run than
deploy.js.txt.

## Confirmation gates

1. **Typed site confirmation.** The operator must type the site's leaf
   path before anything happens.
2. **Permission preflight.** ManageLists + ManagePermissions are
   verified up front.
3. **Per-list non-empty gate.** A list that still contains items is
   *refused*, unless every item carries the `[DEMO]` Title marker
   (demo-only content proceeds automatically), or the operator types
   `DELETE NON-EMPTY` for **that specific list**. One confirmation never
   authorises deleting any other non-empty list.

## Recycle-first teardown

Retention-governed sites refuse to delete a list that still contains
items, while an emptied list deletes fine (live-confirmed). Rollback
therefore empties lists before deleting them, via `recycle()`, never a
permanent delete, so every item remains restorable from the recycle bin:

- **Demo path:** every row's `[DEMO]` marker is re-checked at the
  moment of recycling; an unmarked item aborts that list, fail closed.
- **Override path:** after `DELETE NON-EMPTY`, all items are recycled.
  The operator just authorised deleting the list including its contents,
  and emptying first is what makes the delete succeed under retention.

A paging safety stop aborts if a list fails to drain.

## Protection handling

A list deployed with `prevent_list_deletion` (or locked by hand) has
`AllowDeletion` off. Rollback unlocks it only once deletion of that list
is authorised, and re-locks it if the delete fails. The protection is
never left stranded off. Sealed *columns* need no counterpart: list
deletion never consults per-field `Sealed` (every out-of-the-box list
carries built-in sealed fields and deletes fine).

## When SharePoint still refuses

If an **emptied** list is still refused under a hold/retention message,
a site-level hold applies. That is compliance enforcement the script
will never bypass: it prints a targeted advisory naming the situation
(including that a delay hold can persist after release) and stops. A
compliance administrator must release the hold before rollback can
proceed.

## Honest failure output

Delete failures carry SharePoint's own `error.message.value`, not a bare
HTTP status. A blocked teardown must be diagnosable from the console
transcript alone.
