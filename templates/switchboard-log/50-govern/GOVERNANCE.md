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
[templates/HEALTHCARE.md](../../HEALTHCARE.md).

## The code log review (the record's whole purpose)

- **After every real event**: the switchboard manager checks the row is
  complete (times, all-clear, notes) within one business day — while
  memory works. Missing all-clears are the classic gap; chase them.
- **Monthly** (emergency planning committee): the *Code log* view —
  activations by type, durations, drill coverage per code type, and
  anything the notes flag (paging failures, contact lists that didn't
  work). The log is the committee's evidence base; feed fixes to the
  improvement-register.
- **Drill coverage**: every code type your procedures require gets
  drilled on its schedule — the IsDrill filter makes the coverage gap
  visible in one view.

## Message escalation (edit to your after-hours procedures)

| Urgency | Relay target | If unreachable |
|---|---|---|
| Emergency | Immediately, interrupting other work | Escalate up the on-call chain immediately; log every attempt in the row |
| Urgent | Within 1 hour | Second attempt within the hour, then escalate to the on-call manager |
| Routine | Same shift or next sensible hour | Carries on the Pending board to the next shift |

A message Pending across two full shifts is an incident in the making —
the manager reviews the *Pending relay* view each morning.

## Key audits

- **Weekly**: *Keys out now* reconciled against physical reality; any key
  out longer than its purpose warrants gets chased.
- **Quarterly**: full catalogue audit — every Active key sighted or
  accounted for; lost keys marked Inactive with the loss noted and the
  lock-change decision recorded (security's call, logged here).
- Restrictions on the catalogue are security's to set; operators enforce
  them at the window, and "they insisted" is not an override — the
  escalation is a phone call to the on-call manager, logged.

## Data-quality rules

1. Contemporaneous or marked: anything entered late says so in its notes
   ("entered 07:10 re 03:20 event") — the honest gap rule, as in
   routine-checks.
2. Code events are never edited after the manager's completeness check
   except by appending notes.
3. Messages record who actually received them, not who was attempted.

## Lifecycle

Code and key records are emergency/security evidence — retain long, per
your schedule. Message logs contain personal information — retain per your
records authority, then dispose. Export before decommission; never run
`rollback.js` against real rows.
