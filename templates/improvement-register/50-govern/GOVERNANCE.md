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
the new way replaced the old way (old form retired, procedure updated —
policy-library pairing), the people affected were shown it, and
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

## Lifecycle

Keep everything — Adopted is your evidence base, Abandoned your paid-for
lessons. Export before decommission; never run `rollback.js` against real
rows.
