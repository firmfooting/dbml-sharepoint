# RAID log: governance

## Ownership

| Role | Held by | Accountable for |
| --- | --- | --- |
| Project manager | n/a | The standing item happens; the log is read, not just kept |
| Every risk owner | `RiskOwner` | The rating being current and the review date being met |
| Every action owner | `AssignedTo` | Status truthfulness and delivery |
| Every issue owner | `Owner` | Driving the issue to Resolved, and saying what fixed it |
| Project board or sponsor | n/a | Decisions the project manager cannot make alone; risks escalated upward |
| Site Owners | n/a | Group membership, deploys |

## The two-hand discipline (what makes this work)

RAID is four lists and one reading. Kept as four independent registers it
degrades into four documents nobody opens, which is what happens to the
four-tab spreadsheet this template replaces.

1. **The four are read together, in one standing item, in this order:
   issues, actions, risks due for review, decisions made today.** The order
   is not arbitrary. Issues are the only ones costing the project money
   today; actions are what somebody promised about them; risks are the ones
   that have not cost anything yet; and the decision list is written at the
   end because it records what the meeting just did about the other three.
2. **Two moves connect the lists, and both are one-way.** A risk that
   materialises becomes an **issue**, and the risk is closed with a closure
   note saying which issue it became. An action that exists to reduce a
   risk carries that risk in `RelatedRisk`. Nothing else joins, and nothing
   flows back: an issue never becomes a risk again, because a thing that
   has happened cannot go back to being uncertain.
3. **Actions have one named owner and a real date.** Both columns are
   required, so the list refuses "the team" and "ASAP" before the project
   manager has to.
4. The *Overdue* view is reviewed at every project meeting. Three
   consecutive meetings with the same action overdue is an escalation to
   the project board, not a fourth reminder.
5. The *Review due* view is the risk half of the same rule. A risk log
   where every review date sits in the future is a risk log nobody has
   opened.

## When a risk graduates

**This log holds project risk. It is not the organisational risk
register.** A project risk lives and dies with the project; an
organisational risk outlives it. The two look identical on the day they are
raised and diverge completely afterwards, so the graduation is a deliberate
act rather than something anybody notices.

Move a risk to the organisational register (`risk-register` in this
library, or whatever your organisation mandates) when **any** of these is
true:

- Its consequence lands outside the project: on patient or client safety,
  on statutory compliance, on the organisation's finances or reputation.
- It will still exist after the project closes. A risk about a system the
  project is delivering does not end when delivery does.
- Its owner is not on the project. If the person who can actually act sits
  outside the team, the project cannot own the risk however good the entry.
- A board or executive is being asked to accept or tolerate it. Tolerance
  with an expiry date is an organisational decision.

Graduating is a copy, not a move: raise it on the organisational register,
then close the project row with a closure note naming where it went. The
project keeps its evidence that it spotted the risk, and the two registers
do not hold two half-maintained copies of the same rating. The
organisational register carries the things this template deliberately drops
(category, sponsor, target rating, control effectiveness, a versioned
matrix), which is the other half of why the graduation is worth making
explicit.

## The two lookups, and what they cost

`ProjectAction.RelatedRisk` and `ProjectIssue.RelatedRisk` are the only
joins in the family, and both are nullable. On a project site they are
safe, and the reason is size rather than luck: a project risk log holding
more than a few hundred rows has stopped being a project risk log.

The failure to know about is **not** in the views. A Lookup column's picker
enumerates its target list, and past the 5,000-item list view threshold
that enumeration is refused, so the **new-item form stops working** while
every view that merely displays the column carries on normally. It looks
like a form bug and it arrives late.

The measured lever is the target list's display column. Measured 2026-07-31
at 6,500 items against `GetLookupFieldChoices`, the call the form itself
makes (`test/manual/threshold-index-probe.js`):

| Display column | Result |
| --- | --- |
| `Title`, indexed | served, 2,000 choices |
| a Calculated column | refused, `SPQueryThrottledException` |

So `ProjectRisk.Title` is indexed. It is **not** declared in the
`indexes { }` block in `schema.dbml`, and it should not be added there: the
build appends it because `Title` is the display column of a lookup target,
and that index is the thing keeping both pickers working. A calculated
display column would be the wrong answer twice over, because a calculated
column cannot be indexed at all (setting `Indexed=true` is accepted and
reads back `false`), so there would be no index to create and the picker
would fail the moment the list grew. Do not point a display column at
`ResidualRiskRating` or `RiskScore` for a nicer-looking picker.

If a project risk log is genuinely approaching the threshold, the answer is
not a bigger index. It is that the list is counting something other than
project risks, or that the project should have graduated most of them.

## Matrix change control

The matrix is encoded in `20-configure/mapping.yaml`, in the
`ResidualRiskRating` and `RiskScore` formulas. **Editing a cell
recalculates every existing row**: SharePoint recalculates a calculated
column's formula across the whole list the moment the formula text changes,
and a redeploy is exactly that change.

`risk-register` guards this with a `MatrixVersion` column, so a row stamped
to an older matrix goes blank rather than being silently re-rated. **This
template drops that guard**, and the trade is worth being explicit about,
because it is the one place a RAID log is weaker than the register it
borrowed the matrix from.

The reasoning: a project log is created with the project and archived with
it, so it does not outlive a revision of the matrix, and carrying the
column, the enum and the version literals would be three things to explain
for a case that does not arise. The cost is that if you *do* revise a cell
mid-project, every existing row is re-rated by the new matrix with no
record that it was ever rated differently.

So the discipline is:

1. Set the matrix **before first deploy**, or accept that changing it
   re-rates history.
2. If a cell has to change mid-project, export the risk list to Excel
   first. That snapshot is the only record of the ratings as they stood.
3. Update the ASCII matrix table in the comment above
   `calculated_formulas` to match the cells you changed. It is what the
   next person reads before touching one.
4. Bump `schema_version` in `release.yaml`, rebuild, redeploy, and tell the
   risk owners their ratings moved.
5. A project that needs to re-rate under a revised matrix *and* keep the
   old ratings has outgrown this template. That is `risk-register`.

The two formulas are keyed to exactly the five `raid_likelihood` and five
`raid_consequence` members, in the order the schema declares them: the
nested IFs match the first four by name and treat everything else as the
fifth. An added, renamed or reordered member therefore rates as the worst
case silently rather than failing. Changing either enum means rewriting all
25 cells.

## Enforcement boundary

Four rules refuse a save. Everything else on this page is a discipline, and
the difference is worth knowing rather than assuming:

| Rule | Where it lives | Why there |
| --- | --- | --- |
| An action cannot be dated done in the future | **Enforced at save**, on the column | Reads only its own column, so it keeps its own message. A forward-dated completion sorts to the top of *Done and dropped* and reads as the most recent thing the project finished |
| An issue cannot be dated resolved in the future | **Enforced at save**, on the column | Same shape, same reason |
| Action Status **Done** needs a completed date | **Enforced at save**, on the list | An action finished on a date nobody can name is still In progress |
| Issue Status **Resolved** or **Closed** needs a resolved date | **Enforced at save**, on the list | The same claim about an issue. "It went away at some point" is not a resolution |
| Action Status **Dropped** needs a note | **Governance check**, deliberately | Dropping is already the honest move against leaving a row Open forever. A template whose first act is to make the honest move harder than the dishonest one has its incentives backwards |
| A closed risk says why, in Closure Note | **Governance check**, forced | `ClosureNote` is rich text, and a SharePoint validation formula cannot reference a rich-text column at all. Nothing can enforce this; the review is the control |
| One named owner on every row, never "the team" | **The schema**, not a rule | `RiskOwner`, `AssignedTo` and `Owner` are single person columns and required, so "the team" is not a value they can hold |
| A rating that matches the matrix | **The schema**, not a rule | The rating is calculated, so there is nowhere to type one that disagrees |
| Review dates being met | **Governance check** | The *Review due* view is the surface; opening it at the standing item is the cadence |
| Decisions are append-only in spirit | **Governance check** | Nothing can distinguish a corrected typo from a rewritten decision. Version history is the evidence; the habit is the control |

Two rules that were considered and are **not** expressible, so nobody
spends an afternoon on them: nothing can react to `ResidualRiskRating`,
because conditional visibility and validation cannot read a calculated
column, and nothing can require an issue to name the risk it came from,
because most issues legitimately have no risk behind them.

## Sealed columns and deletion protection

Every deployed column is sealed and every list carries deletion protection.
Neither is an access control: a site owner or tenant administrator bypasses
both, and the deployer itself unseals for its own run and re-seals
afterwards. What they buy is that a well-meaning change through the list
settings UI is refused rather than silently applied, and that the ones
still possible (a display-name rename) are drift the next re-paste reverts
and reports. `rollback.js.txt` clears deletion protection per list, after
you confirm that list.

## Data-quality rules

1. Every open risk carries a review date that has been moved forward at
   least once. A review date still holding its original value months later
   means the risk has never been reviewed.
2. Every closed risk carries a closure note. This one cannot be enforced,
   which is exactly why it is checked.
3. `CompletedDate` accompanies every Done action, and `ResolvedDate` every
   Resolved or Closed issue. Both are enforced at save.
4. An issue that came from a logged risk carries `RelatedRisk`. Missing
   links are the project quietly losing the evidence that it saw the thing
   coming.
5. A decision whose Detail says only what was decided, and not why or who
   disagreed, is half a decision. It will be reopened.

## Lifecycle

Keep everything for the life of the project, then archive the whole family
with the project record. Nothing here is deleted in flight: closed risks,
dropped actions and resolved issues are the entire content of a lessons
session, and a log pruned to only the live rows cannot answer what the
project already dealt with.

At project close, export all four lists before decommissioning the site,
and check the risk log one last time for anything that should graduate to
the organisational register rather than be archived with the project.
Never run `rollback.js.txt` against real rows.
