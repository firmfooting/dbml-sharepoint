# Meeting actions — governance

## Ownership

| Role | Held by | Accountable for |
| --- | --- | --- |
| Forum chair (per meeting type) | — | Actions reviewed at each meeting; decisions recorded |
| Every action owner | `AssignedTo` | Status truthfulness and delivery |
| Site Owners | — | Group membership, deploys |

## The follow-up discipline (what makes this work)

1. **Every meeting opens with the previous meeting's actions.** This single
   rule is the difference between a register and a graveyard. The surface
   is the *By meeting* view, opened at that meeting's group.
2. Actions have **one named owner and a real date** — chairs bounce
   anything assigned to "the team" or dated "ASAP". Both columns are
   required, so the list bounces them first.
3. The *Overdue* view is reviewed weekly by each forum's chair; three
   consecutive overdue reviews of the same action escalate it to the
   chair's own manager or forum.

## What is enforced at save, and what stays a governance check

Two rules refuse a save. Everything else on this page is a discipline, and
the difference is worth knowing rather than assuming:

| Rule | Where it lives | Why there |
| --- | --- | --- |
| An action cannot be dated done in the future | **Enforced at save**, on the column | Reads only its own column, so it keeps its own message. A forward-dated completion sorts to the top of *Done and dropped* and reads as the most recent thing the team finished |
| Status **Done** needs a completed date | **Enforced at save**, on the list | Data-quality rule 2 below, made real. An action finished on a date nobody can name is still In progress |
| Status **Dropped** needs a note | **Governance check**, deliberately | Dropping is already the honest move against leaving a row Open forever. A template whose first act is to make the honest move harder than the dishonest one has its incentives backwards |
| One named owner, never "the team" | **The schema**, not a rule | `AssignedTo` is a single person column and required, so "the team" is not a value it can hold |
| Decisions are append-only in spirit | **Governance check** | Nothing can distinguish a corrected typo from a rewritten decision. Version history is the evidence; the habit is the control |
| That a meeting's actions were actually reviewed | **Governance check** | The *By meeting* view is the surface; opening it is the cadence |

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
2. `CompletedDate` accompanies every Done. This one is enforced at save.
3. Quarterly, each chair skims their forum's decision log for anything that
   silently lapsed — lapsed decisions get an explicit superseding entry.
   The *By meeting* view on Decision is the per-forum read.

## Lifecycle

Keep everything — the register IS the corporate memory and it's tiny data.
Export before decommissioning; never run `rollback.js.txt` against real rows.
