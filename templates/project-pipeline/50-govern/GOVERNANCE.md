# Project pipeline — governance

## Ownership

| Role | Held by | Accountable for |
|---|---|---|
| Pipeline owner | *(e.g. PMO lead / COO / planning manager)* | Gate cadence, scoring definitions, this document |
| Sponsor (per proposal) | The `Sponsor` executive | Scoping honesty; delivery if approved |
| Gate | *(the forum below)* | Decisions, recorded |

## Rating definitions (edit, then hold the line)

**Benefit** — High: material impact on strategy, safety, revenue or many
staff/customers. Medium: clear improvement for a team or process. Low: nice.

**Feasibility** — Easy: known approach, capability on hand, few
dependencies. Moderate: some unknowns or dependencies. Hard: novel,
contended resources, external dependencies.

Score = Benefit × Feasibility (1–9). It ranks the conversation; it doesn't
end it — a strategic Hard/High (score 3) can absolutely beat a trivial
Easy/Medium (6). The gate's job is to overrule the score *out loud*.

## Gate authority (edit to your delegations)

| CostBand | Decided by | Cadence |
|---|---|---|
| Minimal / Small | Pipeline owner + relevant manager | Monthly |
| Medium | Executive team | Monthly |
| Large | Executive team / board per your delegations | As required |

Every gate outcome gets `DecisionDate` + `DecisionNotes` (who, why). An
Approved without a named Sponsor is returned to Scoping.

## Portfolio review

- **Monthly**: the gate works the *Decision queue*; the pipeline owner
  reports the funnel (counts per stage, time-in-stage outliers).
- **Quarterly**: the *Portfolio* view against capacity — approving more
  than you can deliver is how pipelines die; Parked exists so "yes later"
  doesn't rot as "yes".
- **Annually**: the Graveyard read-through — patterns in what gets declined
  are strategy telling you something.

## Data-quality rules

1. Ready for decision requires Problem, Outcome, Benefit, Feasibility,
   CostBand and a Sponsor.
2. Declined/Parked always carry DecisionNotes — the graveyard is only
   useful annotated.
3. Ideas older than 6 months without movement get a nudge, then Parked with
   "no sponsor found" — honest funnels shrink.

## Lifecycle

Keep everything; the pipeline's history is your planning memory. Export
before decommission; never run `rollback.js` against real rows.
