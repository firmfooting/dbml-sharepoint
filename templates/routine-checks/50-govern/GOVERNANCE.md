# Routine checks — governance

## Ownership

| Role | Held by | Accountable for |
|---|---|---|
| Checks owner | *(e.g. quality/facilities/NUM per area)* | The catalogue, missed-check monitoring, this document |
| Checkpoint owner (per row) | `CheckPoint.Owner` | That checkpoint's completeness and follow-up |
| Everyone on the rounds | — | Timely, truthful entries |

## Out-of-range escalation by check type (edit; mirror into Instructions)

| Check type | Immediate action | Escalate to |
|---|---|---|
| Temperature - cold chain | Protect stock per your cold-chain policy; do not use until cleared | Pharmacy/immunisation lead same shift — breach protocol applies |
| Safety equipment | Restock/replace before walking away | Area manager if unable |
| Cleaning / environment | Rectify or log a service request | Facilities per your thresholds |
| Security round | Per your security procedure | Duty manager |

## Missed-check monitoring (the discipline the paper never had)

SharePoint can't nag; people must look — but now looking is trivial:

- **Daily** (checkpoint owners or the checks owner): the *Today* view —
  every Active checkpoint of daily-or-better frequency has its entries.
  Gaps are followed up **that day** while the cause is fresh.
- **Weekly** (checks owner): the *Out of range* view — every entry has an
  Action taken; *escalated* entries reached their escalation point.
- **Monthly**: completeness rate per checkpoint (entries ÷ expected) —
  chronic gaps are a rostering/design conversation, and a checkpoint
  nobody can sustain gets redesigned, not ignored.

## The retrospective-entry rule (write it, enforce it)

Entries are made at the time of the check. Reconstructed entries are
prohibited; a missed check is recorded by its absence and managed as a
gap. Timestamps are attributed and versioned — this rule is checkable,
and being checkable is what makes the register audit-grade.

## Data-quality rules

1. Every Active checkpoint: range, frequency, instructions, owner.
2. Out-of-range entries always carry Action taken.
3. Retired checkpoints go Inactive; their history stays.

## Lifecycle

Check histories are compliance evidence (cold chain especially) — retain
per your schedule. Export before decommission; never run `rollback.js`
against real rows.
