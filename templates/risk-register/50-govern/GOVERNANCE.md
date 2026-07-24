# Risk register — governance

## Ownership

| Role | Held by | Accountable for |
|---|---|---|
| Register owner | *(e.g. CFO / COO / risk lead)* | Register completeness, escalation, the matrix, this document |
| Risk owner (per row) | The `Owner` column | Rating honesty, treatment, reviews |
| RR Risk Managers | The maintaining group | Data entry and upkeep |

## Review cadence by rating

| Rating | Reviewed at least | Reported to |
|---|---|---|
| Extreme | Monthly | Executive / board — every cycle |
| High | Quarterly | Executive summary |
| Medium | Six-monthly | Register owner |
| Low | Annually | Register owner |

Set each row's `ReviewDate` accordingly when the rating changes; the
*Reviews overdue* view is the register owner's weekly first stop.

## Acceptance and escalation rules (edit to your delegations)

- **Accepted** status requires recorded sign-off: Medium by the risk owner's
  manager; High by the responsible executive; Extreme by the CEO/board.
  Record who/when in Detail.
- A risk newly rated **Extreme** is escalated to the executive within one
  business day of rating — the register records it; the escalation is a
  conversation.

## Matrix change control

The matrix is encoded in `20-configure/mapping.yaml` and **a redeploy
re-rates every existing row** (SharePoint recalculates calculated columns on
formula change). Before changing any cell:

1. Export the register to Excel — that snapshot preserves the old ratings.
2. Change the cells and the DBML enums together if wording changes; bump
   `schema_version`; redeploy.
3. Note the matrix change and date here, and have risk owners re-confirm
   ratings at their next review.

## Data-quality rules

1. No Open/Treating risk without Owner, Controls and a future ReviewDate.
2. Consequence is "worst credible", agreed at review — not re-argued weekly.
3. Closed risks keep their history; a recurrence is a new row referencing
   the old.

## Lifecycle

Export before decommissioning; never run `rollback.js` against a populated
register.
