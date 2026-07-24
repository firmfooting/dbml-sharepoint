# Training register — staff guide

## For all staff

**Checking your coverage.** Open **TR_TrainingRecord** → the *By person*
view → your name. That's your training record as the organisation knows it.
If a completion is missing, send the certificate/evidence to a Training
Coordinator — staff don't edit records themselves, because the register is
compliance evidence.

**When something expires.** Coordinators mark records **Expiring** ahead of
the date. If a mandatory record of yours goes Expiring: booking the refresher
is your job; recording the completion is theirs.

## For training coordinators

### Recording a completion (1 minute)

1. **TR_TrainingRecord** → **New**.
2. **Person**, **Course** (from the catalogue — never free-typed),
   **Completed date**.
3. **Expiry date** = completion + the course's validity months; leave blank
   only for never-expiring courses.
4. **Evidence URL**: link the certificate where it's stored. A record
   without reachable evidence is a claim, not a record.

### Maintaining the catalogue

New requirement → add the **Course** first (with `ValidityMonths` and
`Mandatory`), then record completions against it. Don't repurpose an
existing course row for different content — retire it in Notes and add a
new one, or history becomes ambiguous.

### The weekly expiry sweep (10 minutes)

1. Open *Expiring 60 days* → set those records' Status to **Expiring** and
   notify the person and their manager.
2. Anything past its ExpiryDate → Status **Expired** — and escalate per the
   governance rules if the course is mandatory.
3. When the refresher is completed → record it as a **new row** (don't
   overwrite the old one; the history is the audit trail), and set the old
   row **Expired**.
