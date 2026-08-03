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
  *Auto-renewals* views — both deploy with the list, so there is nothing to
  build first. Every row expiring inside its notice period gets a renewal
  decision recorded (Status → In renewal, or an exit plan). Note the
  ninety days is a **rolling** window, not a calendar quarter: CAML has no
  calendar-period predicate, so a quarter-boundary reading has to come from
  your own reporting.
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

## What the list enforces, and what this document does

Three of those rules are now refused at save. The rest are yours.

**Enforced at save — SharePoint rejects the row:**

| Rule | Where it lives | Message shown |
|---|---|---|
| An **Auto-renews** contract must carry a notice period | list validation | Names the notice period as the only thing standing between the contract and a renewal nobody chose |
| `NoticePeriodDays` cannot be negative | column validation | Its own message, on the column |
| `AnnualValue` cannot be negative | column validation | Its own message, on the column |

A cross-column rule shares the list's single `ValidationFormula`, which is
why only the first is written that way and the other two live on their
columns, where each keeps its own message.

**Still a governance check — nothing stops a wrong entry:**

- **`EndDate` after `StartDate`.** The condition grammar compares a column
  to a literal, never to another column, so the rule has no spelling at
  all. A reversed pair sorts to the top of *Live contracts* (soonest expiry
  first) years in the past, which is the compensating control: the monthly
  review sees it immediately.
- **`Owner` present and current.** Person columns cannot appear in a
  SharePoint validation formula, so "an Active contract needs an owner"
  cannot be enforced. The annual ownership sweep below is the control.
- **`AnnualValue` being *right*.** A save rule can only refuse a negative
  number; it has no opinion about a plausible wrong one.
- **The notice period being the *contract's* notice period.** The save rule
  proves a number is present, not that it matches the signed document. That
  is what the quarterly spot-check is for.

Where the form helps rather than enforces: `NoticePeriodDays` disappears
when `RenewalType` is *Fixed term — no renewal*, so the field is on screen
exactly when it can be mandatory. SharePoint cannot clear a hidden field's
value, so a notice period entered before the type was switched survives —
harmless, since nothing reads it in that state.

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
  generated `rollback.js.txt` against a register containing real rows.
