# Switchboard log — governance

## Ownership

| Role | Held by | Accountable for |
|---|---|---|
| Switchboard manager | *(e.g. support services / corporate services manager)* | Operator habits, reviews, this document |
| SB Switchboard Operators | The operating group | Contemporaneous, truthful logging |
| Emergency planning committee | — | Consuming and reviewing the code log |
| Security / facilities | — | The key catalogue and its restrictions |

## Sector note — healthcare

Code events reference clinical situations without containing them: "Code
Blue - Ward 2 North, MET team paged" is a switchboard record; the
patient's deterioration and treatment live in clinical systems. Operators
log what switchboard *did*, never what clinicians found. See
[templates/healthcare.md](../../healthcare.md).

The seeded demo data holds nothing clinical, for the same reason.

## The code log review (the record's whole purpose)

- **After every real event**: the switchboard manager checks the row is
  complete (times, all-clear, notes) within one business day — while
  memory works. Missing all-clears are the classic gap, and the **Still
  running** view is now where they show: any code with no all-clear sits
  there, and its All Clear At cell reads "Running" in red in every view
  until somebody closes it.
- **Monthly** (emergency planning committee): the **Code log** view —
  activations by type, durations, and anything the notes flag (paging
  failures, contact lists that didn't work). **Real events only** strips
  the drills out when the question is about real activations.
- **Drill coverage**: **Drills** is grouped by code type, collapsed. A
  code type with no group is a code type nobody has drilled — which is
  what makes the coverage *gap* visible rather than just the coverage.

## Message escalation (edit to your after-hours procedures)

| Urgency | Relay target | If unreachable |
|---|---|---|
| Emergency | Immediately, interrupting other work | Escalate up the on-call chain immediately; log every attempt in the row |
| Urgent | Within 1 hour | Second attempt within the hour, then escalate to the on-call manager |
| Routine | Same shift or next sensible hour | Carries on the Pending board to the next shift |

A message Pending across two full shifts is an incident in the making —
the manager reviews the **Pending relay** view each morning. An
**Emergency** message still pending washes its whole row there, which is
this list's one row-level signal and is reserved for exactly that.

**Relay times** is where the targets above are checked: relayed messages
from the last thirty days, grouped by urgency band, each with its own
minutes-to-relay and a bar, and a **mean minutes-to-relay under each
urgency band** — which is the number the targets above are actually
judged on. One limit worth knowing before a figure from it goes anywhere:
the window is a **rolling** thirty days, not a calendar month, because
CAML has no calendar predicate. A calendar-month figure still needs an
export.

## Key audits

- **Weekly**: **Keys out now** reconciled against physical reality; **Out
  since before today** is the narrower chase list, and any key out longer
  than its purpose warrants gets followed up.
- **Quarterly**: full catalogue audit from **The key register** — every
  Active key sighted or accounted for. **By key** is the working surface:
  expand a key and read every movement it has ever had. Lost keys are
  unticked rather than deleted, with the loss noted and the lock-change
  decision recorded (security's call, logged here); they then appear in
  **Retired and lost keys** and leave the register automatically.
- Restrictions on the catalogue are security's to set; operators enforce
  them at the window, and "they insisted" is not an override — the
  escalation is a phone call to the on-call manager, logged.

## What is enforced at save, and what stays a governance check

| Enforced at save | Rule |
|---|---|
| `Key.KeyRef` | Unique across the catalogue (a schema constraint) |
| Every datetime column on all three logs | None may be in the future |
| `MessageLog` list | **Relayed** needs both a Relayed To and a Relayed At |
| `KeyMovement` list | **Returned** needs a Returned At |

The message rule is data-quality rule 3 below, and it is the one the whole
message book stands on: a message marked Relayed with no name and no time
is a 2 a.m. call with no trail. It is also why the two relay fields appear
on the form the moment Status becomes Relayed — a refusal naming a field
the operator cannot see is what conditional visibility exists to prevent.

Two rules stay governance checks, and the reasons are structural rather
than oversights:

- **Code-event completeness.** `EventNotes` is rich text, and SharePoint
  validation formulas cannot reference rich text at all. And a rule
  requiring an All Clear At would refuse to save the row at the moment a
  code is *announced* — which is precisely when it must be recorded, with
  two fields, during an emergency. Making the record impossible to start
  in order to force it to be finished is the wrong trade. **Still
  running** plus the red "Running" cell is the control, and it is a
  visible one.
- **Contemporaneous entry** (data-quality rule 1). A row typed at 07:10
  about a 03:20 event saves exactly like one typed at 03:20. Nothing in
  the platform can tell them apart at save time, and a rule tight enough
  to try would refuse the legitimate case — an operator who was busy
  running the code. The marked-late note in the row and item version
  history are what carry it, and version history is where an auditor
  looks.

## Data-quality rules

1. Contemporaneous or marked: anything entered late says so in its notes
   ("entered 07:10 re 03:20 event") — the honest gap rule, as in
   routine-checks. **Not enforceable — see above.**
2. Code events are never edited after the manager's completeness check
   except by appending notes.
3. Messages record who actually received them, not who was attempted.
   **Enforced at save.**

## Lifecycle

Code and key records are emergency/security evidence — retain long, per
your schedule. Message logs contain personal information — retain per your
records authority, then dispose. Export before decommission; never run
`rollback.js.txt` against real rows.
