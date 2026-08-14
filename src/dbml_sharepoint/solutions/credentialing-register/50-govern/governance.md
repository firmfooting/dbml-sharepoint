# Credentialing register: governance

## Ownership

| Role | Held by | Accountable for |
| --- | --- | --- |
| Credentialing authority | *(medical director / DON / credentialing committee)* | Scope decisions; this register reflecting them |
| CR Credentialing Coordinators | The maintaining group | Register accuracy, sweeps, evidence links |
| Every practitioner | n/a | Telling coordinators when their details change |
| Managers | n/a | Not rostering outside recorded scope |

## Decision authority (edit to your framework)

| Decision | Made by |
| --- | --- |
| New scope of practice / changes to scope | Credentialing committee (or its delegate per your by-laws) |
| Temporary/emergency privileges | Per your by-laws, recorded here within 1 business day, flagged in Notes |
| Suspension or conditions | The authority above; register updated the same day |

The register records decisions; it never substitutes for the process. A
row without a committee reference in Notes is a data-entry error.

## Review cycles (set per discipline; defaults below)

| Discipline | Scope review at least every |
| --- | --- |
| Medical / dental | 3 years (or per appointment term) |
| Nursing / midwifery / allied health | 3 years |
| Any practitioner with conditions | Annually, or as the conditions state |

Registration and credential expiries run on the monthly sweeps regardless
of the scope cycle.

## Escalation

Expired professional registration or a lapsed mandatory credential on a
**Current** practitioner: coordinator notifies the credentialing authority
and the practitioner's manager the same day; the practitioner's Status
goes **Under review** until resolved, which puts them in the *Under review
or lapsed* view and keeps their dates coloured rather than muting them.
Whether duties are restricted is the authority's call, made through your
clinical governance process, recorded here, decided there.

## Privacy

- Professional data only: registrations, credentials, scope, conditions.
  No health information, no performance commentary, no complaint detail.
- Site membership is a deliberate decision: default is all-staff read
  (operational who-may-do-what); if your context requires restriction,
  scope the site and record the decision here.
- Subject access: practitioners may see their rows at any time (they can;
  it's the point).

## What is enforced at save, and what stays a governance check

Four rules refuse a save. Everything else on this page is a discipline,
and the difference matters here more than in most registers: an
accreditor's question is *how did the organisation know*, and "the system
would not have let us" is only an answer for the four rows below.

| Rule | Where it lives | Why there |
| --- | --- | --- |
| A scope cannot be approved in the future | **Enforced at save**, on the column | Reads only its own column, so it keeps its own message. A forward-dated approval schedules a review after the one it replaces |
| A credential cannot be issued in the future | **Enforced at save**, on the column | Same shape; the date should be the one on the document you sighted |
| A **Current** practitioner needs a scope-approved date | **Enforced at save**, on the list | "Rows follow decisions, never precede them": this is the half of that a formula can hold |
| A credential marked **Expired** needs an expiry date | **Enforced at save**, on the list | Expired is a claim about a date, and a claim with no date behind it cannot be checked by anyone. **Withdrawn** is deliberately excluded: a credential withdrawn by its issuing body may never have carried an expiry |
| That `ScopeSummary` carries the **approved wording** | **Governance check** | ScopeSummary is rich text, and SharePoint validation formulas cannot reference a multi-line column at all. There is no formula to write. The form header carries the instruction instead, on every open |
| No **Current** credential without linked, sighted evidence | **Governance check**, and the *Missing evidence* view | *Sighted* is unenforceable in principle; a rule that passed on a link to the wrong document would buy nothing. *Linked* is at least checkable, and the view is where it gets checked |
| That a row carries its committee reference in Notes | **Governance check** | A free-text reference cannot be validated into meaning something |
| Whether duties are restricted after a lapse | **Governance check**: the escalation below | The authority's call, made through clinical governance. Recorded here, decided there |

## Data-quality rules

1. No Current credential without linked, sighted evidence. Nothing refuses
   the save; *Missing evidence* is the control, worked to empty weekly.
2. Scope wording is verbatim from the decision, conditions included.
3. Ceased practitioners are never deleted. The historical record is the
   register's legal value. They leave every working view and their stale
   dates stop being coloured; that is retention, not removal.

## Lifecycle

Retention per your clinical governance/records schedule (long). Export
before decommission; never run `rollback.js.txt` against real rows.
