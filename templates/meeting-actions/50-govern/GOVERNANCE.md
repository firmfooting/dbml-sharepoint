# Meeting actions — governance

## Ownership

| Role | Held by | Accountable for |
|---|---|---|
| Forum chair (per meeting type) | — | Actions reviewed at each meeting; decisions recorded |
| Every action owner | `AssignedTo` | Status truthfulness and delivery |
| Site Owners | — | Group membership, deploys |

## The follow-up discipline (what makes this work)

1. **Every meeting opens with the previous meeting's actions.** This single
   rule is the difference between a register and a graveyard.
2. Actions have **one named owner and a real date** — chairs bounce
   anything assigned to "the team" or dated "ASAP".
3. The *Overdue* view is reviewed weekly by each forum's chair; three
   consecutive overdue reviews of the same action escalate it to the
   chair's own manager or forum.

## Decision hygiene

- Decisions are **append-only in spirit**: a changed mind is a *new*
  decision row referencing the old one in Detail, made at a recorded
  meeting. Version history backs this, but the habit matters more.
- Anything with legal, financial or HR consequence still follows its formal
  approval process — this log records that it happened, it doesn't replace
  the authority.

## Data-quality rules

1. Meetings without at least a decision or an action are fine — record them
   anyway; the gap itself is information.
2. `CompletedDate` accompanies every Done.
3. Quarterly, each chair skims their forum's decision log for anything that
   silently lapsed — lapsed decisions get an explicit superseding entry.

## Lifecycle

Keep everything — the register IS the corporate memory and it's tiny data.
Export before decommissioning; never run `rollback.js` against real rows.
