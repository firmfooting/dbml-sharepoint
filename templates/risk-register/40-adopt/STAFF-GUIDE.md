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
   the matrix, not typed in — they are not on the New or Edit form. If a
   rating feels wrong, argue with Likelihood and Consequence, not the
   matrix.
4. Save, and tell the **Risk Sponsor**. Moving Status from Provisional to
   **Open** is the Sponsor's step, not yours — a Provisional risk sitting
   unopened is something to chase the Sponsor about, not something to
   re-save yourself.

> **You need to be in the RR Risk Managers group to edit anything here.**
> Being named in Risk Owner or Risk Sponsor does not grant access — those
> columns record accountability, not permission. Everyone else on the site
> has read access. If you have been made the owner or sponsor of a risk
> and the form opens read-only, ask your site owner to add you to RR Risk
> Managers; you are not doing anything wrong.

Provisional is the one status that tolerates a half-finished risk. Past
it, the register requires both **Likelihood** and **Consequence**: without
them there is no rating and no score, so the risk cannot be ranked in
**Open by score**, never appears in **Above target**, and has no next
review date. It would be a risk the register has stopped managing while
still appearing to hold it.

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
and a **Tolerance End Date** field appears, which the register then refuses
to save without — a Tolerate with no expiry is really just an unrecorded
Accept. Your Risk Sponsor should reassess and re-endorse before that date
arrives.

The date field is only on the form while Tolerate is selected, so you will
not see it otherwise. If you switch away from Tolerate the field
disappears but keeps whatever you last typed; nothing is lost if you
switch back.

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

You will not see Last Reviewed Date when raising a new risk: it fills
itself with today's date, which is the baseline every later cadence counts
from. It appears once the risk exists, which is the only point at which
moving it means anything.

It will not accept a date in the future. That is not pedantry — Next
Review Due is counted from it, so a year typed wrong pushes the next
review out by a year and quietly drops the risk off **Reviews due**, where
nobody would notice its absence.

## Closing a risk

Closing needs a **Closure Statement**: why the risk is being closed against
the closure criteria — residual at or below target, all actions closed,
controls verified effective. The field appears once you set Status to
Closed, and is absent when raising a new risk, since closing something you
are still describing is not a thing anyone does.

The register **does** enforce that a closed risk has controls that hold:
Overall Control Effectiveness must read *All reasonable controls in place*
or *Eliminated or within appetite* before Status will accept Closed. A
risk you are still managing your way out of is not closed, it is open.

It cannot enforce the statement itself. Closure Statement is a multi-line
field, and SharePoint validation formulas cannot read those — a limit of
the platform, not a choice. An RR Risk Manager checks it before moving
Status to Closed. See `50-govern/GOVERNANCE.md` for the
enforcement boundary in full.
