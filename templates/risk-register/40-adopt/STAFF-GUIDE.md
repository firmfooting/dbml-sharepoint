# Risk register — risk owners' guide

*Maintained by RR Risk Managers; readable by everyone.*

## Writing a risk that's actually a risk

A risk is an **uncertain future event**, not a problem you already have
(that's an issue) and not a worry ("budget" is a topic, not a risk).

The pattern: **cause → event → consequence**. "Because we depend on a
single supplier (cause), the supplier could fail mid-contract (event),
halting service for weeks (consequence)." Put the event in **Title**; put
the full cause → event → consequence story in **Detail**.

## Raising a risk

1. Create the item. **Status** defaults to **Provisional** — that is
   correct. You are describing a risk, not yet asking anyone to act on it.
2. Fill in **Controls** first — what already exists — then rate the risk
   *as it is with those controls*, not the naked nightmare.
3. Pick **Likelihood** and **Consequence**. The rating and score appear by
   themselves: **ResidualRiskRating** and **RiskScore** are calculated from
   the matrix, not typed in — they are not on the form at all. If a rating
   feels wrong, argue with Likelihood and Consequence, not the matrix.
4. Save, and tell the **Risk Sponsor**. Moving Status from Provisional to
   **Open** is the Sponsor's step, not yours — a Provisional risk sitting
   unopened is something to chase the Sponsor about, not something to
   re-save yourself.

## Target Risk Rating and Levels Above Target

**Target Risk Rating** is where you are aiming, in line with your
organisation's risk appetite. It is a **judgement call, not a
calculation** — set it once with your Sponsor and revisit it at review,
not every time the residual rating moves.

**Levels Above Target** is calculated: how many rating bands the residual
sits above the target (zero or negative means at or under target). Two or
more levels above target shortens the review cadence, whatever the rating
itself would otherwise call for — read it as "the gap between where this
is and where we want it" needing attention in its own right, separate from
how severe the risk is in absolute terms.

## Response and controls

**RiskResponse** is the strategy — Accept, Manage, Tolerate, Transfer,
Terminate or Monitor. **Tolerate is always for a set period**: choose it
and the register refuses to save without a **Tolerance End Date**, because
a Tolerate with no expiry is really just an unrecorded Accept. Your Risk
Sponsor should reassess and re-endorse before that date arrives.

**Treatment** is what you will *change*, with owners and dates — distinct
from **Controls**, what already exists. When a treatment lands, re-rate:
better controls usually mean lower Likelihood or Consequence, and the
matrix will show it.

## Reviews

**NextReviewDue** is calculated, counted from **LastReviewedDate**, and is
not something you set directly. The cadence:

| Trigger | Review at least every |
|---|---|
| Rating is High or Extreme | 3 months |
| Controls are Inadequate or Uncontrolled | 3 months |
| Two or more levels above target | 3 months |
| Response is Manage or Tolerate | 6 months |
| Controls are Partially effective | 6 months |
| None of the above | 12 months |

**Completing a review means updating Last Reviewed Date** — that one edit
is what tells the register you actually looked at the risk again, and it
is what moves NextReviewDue forward. Re-read Detail, re-confirm or change
Likelihood, Consequence and Overall Control Effectiveness first, then
update Last Reviewed Date last, once you're done. Review sooner than the
cadence if anything material changes in between — the date is a ceiling,
not a target.

## Closing a risk

Closing needs a **Closure Statement**: why the risk is being closed against
the closure criteria — residual at or below target, all actions closed,
controls verified effective. It is a rich-text field, so unlike the
Tolerance End Date rule above, the register cannot enforce that you filled
it in — an RR Risk Manager checks it before moving Status to Closed. See
`50-govern/GOVERNANCE.md` for the enforcement boundary in full.
