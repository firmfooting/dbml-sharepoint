# Process register — governance

## Ownership

| Role | Held by | Accountable for |
|---|---|---|
| Programme owner | *(e.g. COO / transformation / improvement lead)* | The worklist, scoring calibration, this document |
| Process owner (per row) | `Owner` | The row's truthfulness; the process itself |
| Function leads | — | Their function's inventory completeness |

## Scoring definitions (calibrate once, publish, hold)

**Criticality** — High: failure stops service delivery, breaches an
obligation, or loses money that matters. Medium: failure degrades a team's
output. Low: inconvenience.

**PainLevel** — Severe: routine rework/errors/delays, or one-person
dependency on a critical process. Moderate: regular friction people have
normalised. Minor: occasional annoyance.

Cross-team calibration matters more than precision: the programme owner
reviews scores across functions after each workshop round and challenges
outliers *in both directions* — heroic under-scoring is as distorting as
lobbying.

## "Digitised" means done (the definition that keeps the dashboard honest)

A process is **Digitised** only when: the new way is the *only* way (the
old form/spreadsheet is retired, not parallel-run forever), the people who
run it have been shown it, and a measure exists that would reveal if it
quietly reverted (pair with the measures-register template). Built-but-
bypassed is **In progress** at best.

## Programme cadence

- **Fortnightly** (programme owner): the worklist — top-scored unstarted
  rows get an explicit decision: start (small → improvement-register or a
  template deployment; large → project-pipeline), defer, or
  **Not worth digitising** with a reason. Deciding *not* to digitise is
  legitimate output; silence isn't.
- **Quarterly**: dashboard to the executive — counts by status, movement,
  and the *Key-person risk* view (High-criticality processes still on paper
  or in spreadsheets), which is the slide leadership actually remembers.
- **Annually**: full inventory refresh per function — a fresh 30-minute
  pass, not a new workshop.

## Data-quality rules

1. Every row has a human Owner; departed owners are reassigned within a
   month.
2. Scores change only with a note in PainNotes saying what changed.
3. `Digitised` rows carry a SystemUrl.

### What is enforced at save, and what stays a governance check

**Refused at save:**

| Rule | Where it lives |
|---|---|
| Planned, In progress or Digitised has a TargetState | `list_validation` |
| ReviewDate is at most twelve months out | `column_validation` on `ReviewDate` |
| Owner, Function, Criticality, CurrentState, PainLevel and DigitisationStatus are present | the columns' own `not null` — always enforced |

The review-date rule sits on its own column because SharePoint gives a
*list* one validation formula and one message, and a rule that reads only
its own column can therefore keep its own wording. It exists because a
review date further out than a year is not a slower cadence — it is a row
that has left the annual refresh, showing as neither due nor overdue while
quietly going stale.

**Still a governance check, and not by choice:**

- **Rule 3, "Digitised rows carry a SystemUrl", is NOT a save rule**, and
  the reason is worth recording rather than leaving as an omission.
  `SystemUrl` is a Hyperlink column, and this repository has not run a
  hyperlink operand through a SharePoint validation formula against a live
  tenant. The documented syntax makes it look fine; so did several other
  things that were not. Unverified is treated as unknown here, so the rule
  ships as a **visual** control instead: `System URL` is a column on the
  **Programme dashboard**, which groups by status and collapses, so a
  Digitised row with no link is an empty cell in a column of links. That is
  a compensating control, not an equivalent one, and the fortnightly
  programme review is where it is read.
- **Rule 1, a human Owner who still exists.** `Owner` is a person column,
  and SharePoint validation formulas cannot read person columns at all.
  Not-blank is enforced by the column's `not null`; whether the person
  still works here is a monthly check. **By function** groups the register
  the way that check is run.
- **Rule 2, a note in PainNotes when a score changes.** `PainNotes` is a
  multi-line column, which validation formulas also cannot read — and no
  formula can tell a note about a score change from any other note. Item
  version history holds the evidence if it is ever needed.
- **The score itself cannot be validated against anything.**
  `DigitisationPriority` is calculated, and SharePoint validation formulas
  cannot read calculated columns — nor can conditional show/hide, which is
  why nothing on this form appears or disappears in response to the score.
  The form's two conditional fields key on `DigitisationStatus` instead: a
  choice somebody makes, rather than an arithmetic result. A rule keyed on
  the score would save cleanly, read back equal, pass the deploy phase and
  never fire.

## Lifecycle

The register is the programme's memory — keep it. Export before
decommission; never run `rollback.js` against real rows.
