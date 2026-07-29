# Improvement register — governance

## Ownership

| Role | Held by | Accountable for |
|---|---|---|
| Improvement lead | *(e.g. quality/CI manager)* | Triage, coaching owners, the reporting, this document |
| Improvement owner (per row) | `Owner` | Running the cycle honestly, updating the row |
| Everyone | — | Raising ideas; feeding the loops |

## Triage (fortnightly, timeboxed, decisions only)

The improvement lead works the *Triage* view. Every Idea leaves with one
of four outcomes — silence is not one of them:

1. **Planned** — an owner (often the proposer, coached) and a small test
   scope agreed;
2. Redirected — it's really a service request, a change request, or a
   project (send it to that register, note where, close as Abandoned with
   "redirected");
3. Parked honestly — "good, not now, revisit when X" in TestNotes;
4. Declined kindly — with the why, to the proposer's face or inbox first.

## Test discipline (the PDSA spine without the poster)

- Small before big: one team/site/fortnight before any rollout.
- A prediction before the test; the measure decides, not the vibe.
- One change per test where possible — bundled changes teach nothing.
- `MeasureBefore` is required at entry **by the form**; the improvement
  lead's job is making sure it's a real number, not a ritual one. Pair
  measures with the measures-register template where the baseline should
  live on as a permanent KPI.

## Adoption criteria ("Adopted" is a system state, not a mood)

An improvement is Adopted when: the measure moved as predicted (or better),
the new way replaced the old way (old form retired, procedure updated in
whatever holds your controlled documents), the people affected were shown
it, and
`MeasureAfter` is recorded. Anything less stays Testing.

## Reporting

- **Quarterly**: adopted improvements with before/after numbers (the only
  slide that sustains executive sponsorship); the *By source* view (are
  complaints/incidents/audits actually feeding improvement, or are the
  loops decorative?); median DaysIdeaToOutcome — improving the improvement
  system.

## Data-quality rules

1. No Testing without a prediction in ChangeIdea; no Adopted without
   MeasureAfter + AdoptedDate.
2. TestNotes are dated and append-only in practice.
3. Redirected items always name their destination register.

### What is enforced at save, and what stays a governance check

**Refused at save:**

| Rule | Where it lives |
|---|---|
| An Adopted or Abandoned improvement has an AdoptedDate | `list_validation` |
| An Adopted improvement has a MeasureAfter | `list_validation` |
| MeasureBefore is present | the column's own `not null` — it has always been enforced |
| RaisedDate is not in the future | `column_validation` on `RaisedDate` |
| AdoptedDate is not in the future | `column_validation` on `AdoptedDate` |

The two list rules share one message, because SharePoint gives a list a
single validation formula and cannot say which branch failed. The two date
rules read only their own column, so they sit there and keep their own
wording — and they earn it: the median `DaysIdeaToOutcome` is a quarterly
report line computed from those two dates and nothing else.

**Still a governance check, and not by choice:**

- **"No Testing without a prediction in ChangeIdea."** `ChangeIdea` is a
  multi-line column, and SharePoint validation formulas cannot read those
  at all — nor can they tell a prediction from a paragraph. The improvement
  lead reads it at triage; the form's description hint asks for it on the
  New form, where SharePoint still shows column descriptions.
- **Three of the four adoption criteria.** "The measure moved as
  predicted", "the new way replaced the old way" and "the people affected
  were shown it" are judgements. Only `MeasureAfter` being recorded is a
  column a formula can read, and it is the one that is enforced. Anything
  less stays Testing, and that remains a decision a person makes.
- **Rule 2, dated append-only TestNotes.** Multi-line again, and
  "append-only in practice" is a habit rather than a state. Item version
  history is the audit trail if one is ever needed.
- **Rule 3, redirected items naming their destination.** A redirect is
  recorded as Abandoned with the destination in TestNotes; the register
  cannot check that a free-text pointer points anywhere.
- **The cycle time cannot be validated against anything.**
  `DaysIdeaToOutcome` is calculated, and SharePoint validation formulas
  cannot read calculated columns — nor can conditional show/hide, which is
  why nothing on this form appears or disappears in response to how long a
  cycle has taken. Both would save cleanly, read back equal and never fire.

## Lifecycle

Keep everything — Adopted is your evidence base, Abandoned your paid-for
lessons. Export before decommission; never run `rollback.js` against real
rows.
