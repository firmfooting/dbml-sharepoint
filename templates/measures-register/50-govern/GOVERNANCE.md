# Measures register — governance

## Ownership

| Role | Held by | Accountable for |
|---|---|---|
| Measurement owner | *(e.g. head of performance/quality)* | The catalogue, change control, the annual cull, this document |
| MR Measure Custodians | The maintaining group | Definition quality, review cadence |
| Measure owner (per row) | `Owner` | The number being right, produced, and reported |

## Definition change control

1. Proposed change goes to the custodians with the reason.
2. If approved: Notes gets a dated entry (old wording → new wording → why),
   `ReviewDate` resets, and **every forum in ReportedTo is notified that
   the series breaks** at the change date.
3. Material changes (different denominator, different anchor) are a new
   measure row; the old one retires with a pointer. Continuity of *name*
   across a discontinuity of *meaning* is how organisations lie to
   themselves by accident.

## The annual measure cull (the discipline nobody else will impose)

Once a year, the measurement owner walks the catalogue asking three
questions of every Active measure:

1. Did anyone **act** on this number in the last year? (Not "look at" —
   act.)
2. Does anyone still receive it? (Check ReportedTo against real agendas.)
3. Would its owner notice if it stopped being produced?

Three noes = **Retired**. Expect to retire 10–20% annually; a catalogue
that only grows is a reporting burden compounding. Retirement is recorded,
not deleted — retired definitions are needed to read old reports.

## Pairings (this register is the theme's connective tissue)

- **process-register**: "Digitised" requires a measure that would reveal
  reversion — register it here.
- **improvement-register**: baselines that deserve to outlive the test
  become registered measures.
- **complaints / incidents / service-requests / audit-actions**: their
  calculated day-counts are natural registered measures — one definition
  each, here.

## Data-quality rules

1. Active measures have an Owner who still exists, a Definition that passes
   the two-strangers test, and at least one real forum in ReportedTo.
2. Every definition change is dated in Notes.
3. ReviewDate is never blank on an Active measure.

## Lifecycle

Retired rows are kept permanently (they decode historical reporting).
Export before decommission; never run `rollback.js` against real rows.
