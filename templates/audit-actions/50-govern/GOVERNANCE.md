# Audit actions — governance

## Ownership

| Role | Held by | Accountable for |
|---|---|---|
| Assurance owner | *(e.g. CFO / head of governance / audit committee secretary)* | Register completeness, committee reporting, this document |
| Audit sponsor (per audit) | The `Sponsor` executive | The management response and its delivery |
| Action owner (per row) | `Owner` | Delivering the agreed action, honest updates |
| AU Audit Coordinators | The maintaining group | Register upkeep, evidence verification, chasing |

## Closure evidence standard (what "done" must prove)

A recommendation closes only when the evidence, on its own, would satisfy
the **next** auditor that the action happened:

- a changed *thing* (policy published, control configured, report produced)
  — linked, not described;
- dated after the recommendation, attributable, and retained where the
  auditor can be shown it;
- for behavioural actions (training, new practice): the records that show
  it occurred, not the intention that it would.

"Superseded by other work" closes as **Risk accepted** with sign-off, never
as Closed.

## Extension and acceptance authority (edit to your delegations)

| Action | Authorised by |
|---|---|
| Extend a Low/Moderate item (once) | Audit sponsor |
| Extend High/Critical, or any second extension | Audit committee (recorded in minutes, RevisedDue updated) |
| Risk accepted | Audit committee on the sponsor's written justification |

## Reporting cadence

- **Weekly** (coordinators): Overdue view worked; chases logged.
- **Per committee cycle**: the *Committee pack* view, plus the quarter's
  closures with DaysLate — the committee sees lateness as a number, not an
  adjective.
- **Annually**: aged-item review — anything open past 12 months is either
  re-committed with a real plan or taken to Risk accepted honestly.

## Data-quality rules

1. Recommendations enter within 10 business days of the final report.
2. No Closed without EvidenceUrl + ClosedDate; no Risk accepted without
   recorded authority. **ClosedDate is enforced at save; EvidenceUrl is
   not** — SharePoint refuses a validation formula that references a URL
   column, so evidence at closure is a coordinator check, not a rule the
   list can hold.
3. Notes are append-only in practice: dated entries, newest first, nothing
   deleted.

## Lifecycle

The register is assurance evidence — retain long (align with your audit
retention schedule). Export before decommission; never run `rollback.js`
against real rows.
