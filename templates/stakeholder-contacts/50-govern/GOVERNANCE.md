# Stakeholder contacts — governance

## Ownership

| Role | Held by | Accountable for |
|---|---|---|
| Register owner | *(e.g. comms/partnerships lead)* | Hygiene cadence, privacy rules, this document |
| Relationship owner (per organisation) | `Organisation.Owner` | The relationship, and its record being current |
| Everyone using it | — | Logging their own interactions |

## Privacy rules (load-bearing — this register holds personal data)

1. Record **business-contact information only**: name, role, work contact
   details, professional interaction notes. No personal phone numbers or
   addresses, no opinions about people, no sensitive attributes — write
   every Note as if the contact will read it, because under privacy law
   they may.
2. Site membership stays scoped to the teams that need it — this is not an
   all-staff directory.
3. Inactive contacts are retained for the history of *interactions*; run an
   annual purge review — contacts inactive for longer than your privacy
   policy's retention window get their contact details cleared (row kept,
   details blanked) so the interaction history survives without holding
   stale personal data.
4. If someone asks what you hold about them, this register is in scope —
   the register owner handles such requests with your privacy officer.

## What is enforced at save, and what stays a governance check

**One** rule refuses a save, and the shortness of that list is the most
important thing on this page. Every other rule here is a discipline, and
none of them is enforceable even in principle:

| Rule | Where it lives | Why there |
|---|---|---|
| An interaction cannot be dated in the future | **Enforced at save**, on the column | This list is a log of what happened. A forward-dated entry sorts to the top of *Recent activity* and reads as the last thing anyone heard from that stakeholder — and walking into a meeting believing it is the failure the register exists to prevent |
| Business-contact information only; no personal details, no opinions, no sensitive attributes | **Governance check** — privacy rule 1 | No formula can read the difference between a professional note and a personal one. The Contact form header carries the instruction instead, at the moment someone is typing |
| Every organisation has a live Owner | **Governance check** — the quarterly cadence | Not expressible: a person column needs an accessor to be compared at all, and CAML refuses every accessor. The **blank group at the end of *By owner*** is the surface — it *is* the unowned list |
| Inactive contacts' details are cleared after the retention window | **Governance check** — privacy rule 3, the annual purge | Retention is a decision about time passing. The *Moved on* view is where it is worked |
| The register is actually being written to | **Governance check** — the annual candid check | *Recent activity* is the surface; a register nobody writes to is a decision to make, not a fact to ignore |

## Hygiene cadence

- **Quarterly** (register owner): *By owner* — every organisation has a
  live Owner (reassign leavers'), and the **blank group** at the end is
  every organisation that has none. Contacts spot-checked for staleness.
- **Annually**: the privacy purge review (rule 3), worked from the *Moved
  on* view; enum review; a candid check of *Recent activity* — a register
  nobody writes to is a decision to make, not a fact to ignore.

## Relationship-ownership rules

1. One Owner per organisation; disputes settled by the register owner.
2. Handover = the leaver walks their successor through *By contact*,
   opening each key contact's group, and Owner fields are updated the same
   week.
3. Sensitive relationships (regulators, media) get their sensitivities
   noted at the **Organisation** level so anyone interacting sees them.

## Lifecycle

Export before decommissioning; deletion at end-of-life follows the privacy
retention rules above rather than blanket keep-everything — this register
is the other one (with onboarding) where deletion is *expected*, not
forbidden. Never run `rollback.js` against real rows.
