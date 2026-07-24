# Contract register — governance

## Ownership

| Role | Held by | Accountable for |
|---|---|---|
| Register owner | *(name a person, e.g. head of procurement/finance)* | Completeness of the register; this document |
| Contract owner (per row) | The `Owner` column | That contract's renewal decisions and data accuracy |
| CT Contract Managers | The maintaining group | Data entry and upkeep |
| Site Owners | IT / site admins | Membership of the groups; deploys |

## Review cadence

- **Monthly**: register owner reviews the *Expiring 90 days* and
  *Auto-renewals* views; every row expiring inside its notice period gets a
  renewal decision recorded (Status → In renewal, or an exit plan).
- **Quarterly**: spot-check 10 rows against source documents (dates, value,
  counterparty). Log the check.
- **Annually**: confirm every `Owner` still exists and accepts ownership;
  reassign leavers' contracts.

## Data-quality rules

1. `EndDate`, `Owner` and `RenewalType` are never knowingly blank on an
   Active row.
2. `AnnualValue` is an estimate — fine — but a *dated* estimate: re-check at
   renewal.
3. `ValueBand`-style thresholds, delegations and approval limits are policy,
   not schema: enforce them in your procurement process and record the
   outcome here.

## Access rationale

Members read, managers contribute, nobody edits schema day-to-day, and Full
Control sits in an **empty** admin group that the deploy script joins and
leaves automatically. Commercial sensitivity beyond that (e.g. hiding value
from all staff) is a site-membership decision — this register inherits the
site's audience.

## Lifecycle

- **Retention**: exited contracts stay in the register (the row is metadata,
  not the record); the signed document's retention follows your records
  schedule in its own system.
- **Decommissioning**: export to Excel first (list → Export); never run the
  generated `rollback.js` against a register containing real rows.
