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

- **Weekly** (coordinators): the *Overdue* view worked and chases logged,
  then the *Awaiting evidence* view read. Both deploy with the list.
  *Overdue* filters on the **committed** date — the revised one where a
  formal extension exists, the original where it does not — so a properly
  extended recommendation drops out of the queue and an unextended one
  does not.
- **Per committee cycle**: the *Committee pack* view, plus
  *Closed, last 90 days* with DaysLate — the committee sees lateness as a
  number, not an adjective. Note the ninety days is a **rolling** window
  rather than a calendar quarter: CAML has no calendar-period predicate,
  and the two differ on the first day of a quarter.
- **Annually**: aged-item review — anything open past 12 months is either
  re-committed with a real plan or taken to Risk accepted honestly.

## Data-quality rules

1. Recommendations enter within 10 business days of the final report.
2. No Closed without EvidenceUrl + ClosedDate; no Risk accepted without
   recorded authority.
3. Notes are append-only in practice: dated entries, newest first, nothing
   deleted.

## What the lists enforce, and what this document does

Rule 2 is half enforced. The `ClosedDate` requirement is a save rule, on
**both** endings — *Risk accepted* is an ending too, and the closure
report filters on that date, so an accepted recommendation without one
would leave every queue and never reach the committee. The `EvidenceUrl`
requirement cannot be a save rule, and the reason is worth reading before
anyone tries to "fix" it.

**SharePoint will not accept a save rule against a link column.** Setting
a validation formula that references one is refused outright, with a
message that names the cause: *"One or more column references are not
allowed, because the columns are defined as a data type that is not
supported in formulas."* That is established against a live tenant rather
than reasoned about — the probe is
`test/manual/hyperlink-validation-operand-probe.js`.

Nor does such a rule fail quietly: it fails the **paste**, at the
validation phase, in front of whoever is deploying. The build refuses the
operand, which turns a failed deploy into a failed build.

The requirement itself stands. It is a closure criterion below, a
verification step in `30-deploy/deploy.md`, and the **Closed, last 90
days** view displays `EvidenceUrl` so that an empty one is visible to the
committee reading it. That is the compensating control, and — given
SharePoint's answer — the only one available.

Rules 1 and 3 cannot be enforced at save either.

**Enforced at save — SharePoint rejects the row:**

| Rule | List | Where it lives |
|---|---|---|
| Rule 2: a *Closed* **or *Risk accepted*** recommendation needs a `ClosedDate` | Recommendation | list validation |
| `ClosedDate` cannot be in the future | Recommendation | column validation |
| `ReportDate` cannot be in the future | Audit | column validation |

The two closure rules share one message, because a SharePoint list has
exactly one `ValidationFormula` and cannot say which branch failed. The
date half is new: `DaysLate` is computed from `ClosedDate`, so a Closed row
without one produced a blank in the exact column the committee reads
lateness from.

The future-`ClosedDate` rule is more important than it looks. `DaysLate`
guards against negative ranges by returning 0, so a recommendation closed
"next month" would have reported as **closed on time**, silently, on that
same number.

**Still a governance check — nothing stops a wrong entry:**

- **Rule 2's recorded authority for a *Risk accepted* ending.** It lives in
  `Notes`, which is rich text, and a validation formula cannot reference a
  multi-line column at all. The extension-and-acceptance table above is the
  control, and *Risk accepted* renders grey rather than green so nobody
  reads it as a delivery.
- **Rule 1, the ten-business-day loading rule.** A rule about a habit, not
  about a row. Nothing on an audit can know how many recommendations should
  have come off it.
- **Rule 3, append-only Notes.** SharePoint versioning is the evidence
  (200 major versions are retained), not a save rule. Every edit is
  recoverable; nothing prevents one.
- **That the evidence link is evidence.** The rule proves a URL is present.
  Only a coordinator reading it proves the closure standard above was met,
  which is what the *Awaiting evidence* view exists for.
- **Extension authority.** Who may set `RevisedDue` is a delegation, not a
  formula. The form hides the field at intake, which is friction, not
  enforcement.

One caveat, recorded rather than hidden: the evidence rule puts a
**hyperlink** column inside a validation formula. This template has shipped
it since before the family standard existed and it is kept, but it has not
been read back from a live tenant. `30-deploy/deploy.md` has a checklist
item that tests it on the first row you close. Until you have run that,
treat the closure-evidence standard as a governance check.

**What the colours do.** *Implemented - awaiting evidence* is amber — the
action is reported done and nobody has checked it. *Risk accepted* is grey.
Only *Closed* is green. `FindingRating` carries the report's own severity
in the same four colours the risk register uses, and `DaysLate` takes its
bar colour from it, so a forty-day-late Critical and a forty-day-late Low
do not look the same to a committee.

## Lifecycle

The register is assurance evidence — retain long (align with your audit
retention schedule). Export before decommission; never run `rollback.js.txt`
against real rows.
