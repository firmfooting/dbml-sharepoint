# Training register — staff guide

## For all staff

**Checking your coverage.** Open **TR_TrainingRecord** → it lands on *By
person*, the default view, with the groups collapsed → open your name.
That's your training record as the organisation knows it, soonest expiry
first. If a completion is missing, send the certificate/evidence to a
Training Coordinator — staff don't edit records themselves, because the
register is compliance evidence.

**When something expires.** Coordinators mark records **Expiring** ahead of
the date. If a mandatory record of yours goes Expiring: booking the refresher
is your job; recording the completion is theirs.

## For training coordinators

### Recording a completion (1 minute)

The form has four sections and runs in that order.

1. **TR_TrainingRecord** → **New**. *Who and what*: a title, **Person**,
   **Course** (from the catalogue — never free-typed).
2. *When*: **Completed date** — the form refuses a date in the future, with
   a message saying so. **Expiry date** = completion + the course's
   validity months; leave blank only for never-expiring courses.
3. *Evidence*: link the certificate where it's stored. A record without
   reachable evidence is a claim, not a record. Nothing refuses the save —
   see the governance doc for why that is a spot-check rather than a rule.
4. *Currency and notes*: **Status is not on the New form.** It defaults to
   *Current*, which is what a new completion is, and the weekly sweep is
   what changes it afterwards.

### Maintaining the catalogue

New requirement → add the **Course** first (with `ValidityMonths` and
`Mandatory`), then record completions against it. Validity months must be
a positive number or blank; blank is how the catalogue says "never
expires", and the *Never expires* view is where you check annually that
each blank is still true rather than a forgotten field. Don't repurpose an
existing course row for different content — retire it in Notes and add a
new one, or history becomes ambiguous.

### The weekly expiry sweep (10 minutes)

1. Open *Expiring 60 days* → set those records' Status to **Expiring** and
   notify the person and their manager. Anything already past its expiry
   date is red with a warning icon before you touch it.
2. Anything past its ExpiryDate → Status **Expired** — and escalate per the
   governance rules if the course is mandatory. The date goes plain once
   you do; from then on the *Expired* view and the chip carry it.
3. When the refresher is completed → record it as a **new row** (don't
   overwrite the old one; the history is the audit trail), and set the old
   row **Expired**.

### Coverage reporting

*By course* groups every **Current** record under its course, collapsed.
The monthly count of covered-versus-headcount per mandatory course reads
straight off the group headers.
