# Training register — governance

## Ownership

| Role | Held by | Accountable for |
| --- | --- | --- |
| Compliance owner | *(e.g. HR / L&D / quality manager)* | The mandatory matrix, escalation, this document |
| TR Training Coordinators | The maintaining group | Records, catalogue, weekly sweep |
| Line managers | — | Acting on Expiring/Expired notifications for their people |

## The mandatory-training matrix (edit to your organisation)

`Course.Mandatory` covers all-staff requirements. Role-specific requirements
don't fit a boolean — maintain them here and review annually:

| Role / group | Required courses | Refresh |
| --- | --- | --- |
| All staff | Induction; Code of conduct | Once; 24 months |
| *(role)* | *(courses)* | *(interval)* |

## Monitoring cadence

- **Weekly** (coordinators): the expiry sweep — Expiring flagged and
  notified; Expired escalated.
- **Monthly** (compliance owner): coverage check per mandatory course
  (*By course* view): count Current vs. headcount; gaps get named owners
  and dates.
- **Annually**: matrix review; catalogue validity months re-confirmed
  against current legislation/accreditation requirements.

## Escalation

Expired **mandatory** coverage: coordinator → line manager on day 1;
compliance owner → responsible executive at day 14; the register row's
Notes record the trail. (Whether lapsed coverage restricts duties is an HR
policy call — record the decision, don't improvise it.)

## What is enforced at save, and what stays a governance check

Three rules refuse a save. Everything else on this page is a discipline,
and the difference is worth knowing precisely rather than assuming the
software has your back:

| Rule | Where it lives | Why there |
| --- | --- | --- |
| Validity months is positive, or blank for never-expires | **Enforced at save**, on the column | Reads only its own column, so it carries a message that names the actual mistake. Written as an OR: SharePoint reads a blank number as zero, and a bare `> 0` would refuse every never-expiring course |
| A completion cannot be dated in the future | **Enforced at save**, on the column | A forward-dated completion pushes the expiry out with it and drops the record off the sweep silently |
| A record marked **Expiring** or **Expired** needs an expiry date | **Enforced at save**, on the list | Cross-column, so it shares the list's single validation formula. Either status is a statement about a date, and without one the record is unfalsifiable |
| A **Current** record links its evidence | **Governance check** — the quarterly spot-check below | There is no verified way to make a URL column an operand in a SharePoint validation formula here, and *linked* is not *sighted* in any case. A rule that passes on a link to the wrong document buys nothing and costs a save |
| Which courses a **role** requires | **Governance check** — the matrix above | `Course.Mandatory` is a boolean and role requirements are not. Nothing in the schema can hold the matrix |
| Whether Expiring/Expired have actually been chased | **Governance check** — the weekly sweep | The *Expiring 60 days* and *Expired* views are the surfaces; acting on them is the cadence |

## Data-quality rules

1. One row per completion — refreshers are new rows, never overwrites.
   Nothing enforces this; overwrite an old row and the register loses its
   ability to show that coverage ever lapsed.
2. Every row links evidence (`EvidenceUrl`); spot-check 10 rows quarterly.
3. Course rows are never repurposed; content changes = new course row.
4. Leavers: records are retained (they're historical evidence), not deleted.
5. Annually, work the *Never expires* view: a blank validity is right for
   an induction and usually a data-entry omission everywhere else, and
   nothing else in the register can tell the two apart.

## Lifecycle

Records retention follows your HR/records schedule — typically employment
plus a statutory period. Export before decommissioning; never run
`rollback.js.txt` against real records.
