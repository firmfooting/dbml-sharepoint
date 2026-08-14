# Project pipeline: governance

## Ownership

| Role | Held by | Accountable for |
| --- | --- | --- |
| Pipeline owner | *(e.g. PMO lead / COO / planning manager)* | Gate cadence, scoring definitions, this document |
| Sponsor (per proposal) | The `Sponsor` executive | Scoping honesty; delivery if approved |
| Gate | *(the forum below)* | Decisions, recorded |

## Rating definitions (edit, then hold the line)

**Benefit**: High: material impact on strategy, safety, revenue or many
staff/customers. Medium: clear improvement for a team or process. Low: nice.

**Feasibility**: Easy: known approach, capability on hand, few
dependencies. Moderate: some unknowns or dependencies. Hard: novel,
contended resources, external dependencies.

Score = Benefit × Feasibility (1–9). It ranks the conversation; it doesn't
end it. A strategic Hard/High (score 3) can absolutely beat a trivial
Easy/Medium (6). The gate's job is to overrule the score *out loud*.

## Gate authority (edit to your delegations)

| CostBand | Decided by | Cadence |
| --- | --- | --- |
| Minimal / Small | Pipeline owner + relevant manager | Monthly |
| Medium | Executive team | Monthly |
| Large | Executive team / board per your delegations | As required |

Every gate outcome gets `DecisionDate` + `DecisionNotes` (who, why). An
Approved without a named Sponsor is returned to Scoping.

## Portfolio review

- **Monthly**: the gate works the *Decision queue*; the pipeline owner
  reports the funnel (counts per stage, time-in-stage outliers).
- **Quarterly**: the *Portfolio* view against capacity. Approving more
  than you can deliver is how pipelines die; Parked exists so "yes later"
  doesn't rot as "yes".
- **Annually**: the Graveyard read-through. Patterns in what gets declined
  are strategy telling you something.

## Data-quality rules

1. Ready for decision requires Problem, Outcome, Benefit, Feasibility,
   CostBand and a Sponsor.
2. Declined/Parked always carry DecisionNotes. The graveyard is only
   useful annotated.
3. Ideas older than 6 months without movement get a nudge, then Parked with
   "no sponsor found". Honest funnels shrink.

### What is enforced at save, and what stays a governance check

**Refused at save:**

| Rule | Where it lives |
| --- | --- |
| Ready for decision has Benefit, Feasibility and CostBand | `list_validation` |
| Anything past the gate (Approved, In delivery, Delivered, Declined, Parked) has a DecisionDate | `list_validation` |
| Delivered has a DeliveredDate | `list_validation` |
| ProposedDate is not in the future | `column_validation` on `ProposedDate` |
| DecisionDate is not in the future | `column_validation` on `DecisionDate` |

The three list rules share one message, because SharePoint gives a list a
single validation formula and cannot say which branch failed. The two date
rules read only their own column, so they sit there and keep their own
wording; time-in-stage is a monthly report line counted from those dates.

**Still a governance check, and not by choice:**

- **Rule 1's Problem, Outcome and Sponsor.** `Problem` and `Outcome` are
  multi-line columns and `Sponsor` is a person column; SharePoint
  validation formulas can read none of the three. The three that *are*
  enforceable are enforced. "An Approved without a named Sponsor is
  returned to Scoping" stays exactly what it says, a gate discipline, and
  the **Portfolio** view groups by sponsor so an unsponsored approval falls
  into a visible empty group rather than hiding in a flat list.
- **Rule 2, DecisionNotes on Declined and Parked.** Multi-line again. The
  decision *date* is enforced; the annotation is what the annual graveyard
  read-through is for, and `Decision notes` is on that view so its absence
  is obvious at exactly the moment it costs something.
- **Rule 3, the six-month nudge.** A save rule cannot fire on the passage
  of time; nothing is being saved on the day an idea turns six months old.
  **The funnel** shows `Proposed date` in the Idea group for this.
- **The score itself cannot be validated against anything.**
  `PriorityScore` is calculated, and SharePoint validation formulas cannot
  read calculated columns at all; nor can conditional show/hide, which is
  why no field on this form appears or disappears in response to the score.
  Both would save cleanly, read back equal and never fire.

## Lifecycle

Keep everything; the pipeline's history is your planning memory. Export
before decommission; never run `rollback.js.txt` against real rows.
