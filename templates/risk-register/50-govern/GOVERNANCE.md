# Risk register — governance

## Ownership

| Role | Held by | Accountable for |
|---|---|---|
| Register owner | *(e.g. CFO / COO / risk lead)* | Register completeness, escalation, the matrix, this document |
| Risk owner (per row) | The `RiskOwner` column | Rating honesty, treatment, reviews |
| Risk Sponsor (per row) | The `RiskSponsor` column | Approving opening, tolerance and closure |
| RR Risk Managers | The maintaining group | Data entry, upkeep, and checking the Closure Statement before a risk closes |

**Naming someone in `RiskOwner` or `RiskSponsor` grants them nothing.**
Those are person columns, not permissions: `list_permissions` gives
Contribute to **RR Risk Managers** and Read to the site's associated
members and owners, under `reconcile: exact`, and SharePoint has no
item-level grant derived from a person column.

So a Risk Owner who is not in RR Risk Managers cannot record their own
review, and a Risk Sponsor who is not in it cannot move a risk from
Provisional to Open, tolerate one, or close one — the acts this table
makes them accountable for.

**Put every named Risk Owner and Risk Sponsor in RR Risk Managers.** If
that group is wider than you want for general data entry, split it: a
second group with Contribute for the accountable people, RR Risk Managers
for the maintainers. What does not work is assuming the person column
carries an edit path, which reads as though it should and does not.

## Status versus RiskResponse

These two columns look similar and answer different questions.

- **Status** is **lifecycle**: is this risk currently being worked?
  `Provisional` → `Open` → `Closed`. Nothing in the schema stops a value
  moving backwards, but the intended flow is that single pass — treat a
  Closed risk reopened, or an Open risk reverted to Provisional, as
  something worth asking about.
- **RiskResponse** is **strategy**: what are we doing about it? `Accept`,
  `Manage`, `Tolerate`, `Transfer`, `Terminate`, `Monitor`. An Open risk can
  hold any response, and the response can change repeatedly while Status
  stays Open — deciding to Manage instead of Accept a risk does not close
  or reopen anything.

Read them together, not as substitutes for each other: "Open + Tolerate" is
a live risk being knowingly carried for a set period; "Closed + Terminate"
is a risk whose source has been eliminated. A risk can also be "Open +
Accept" indefinitely — Accept carries no expiry requirement, unlike
Tolerate.

## Matrix change control

The matrix is encoded in `20-configure/mapping.yaml`, in the
`ResidualRiskRating` and `RiskScore` formulas. **Editing a cell recalculates
every existing row**: SharePoint recalculates a calculated column's formula
across the whole list the moment the formula text changes, and a redeploy
is exactly that change.

The `MatrixVersion` guard exists so that recalculation cannot silently
re-rate history. Both matrix formulas short-circuit to blank when
`[MatrixVersion]` does not equal the current version literal they carry.
Revising the matrix is therefore an **append, not an edit**:

1. Append the new version to the `matrix_version` enum in `schema.dbml`
   (e.g. add `"1.1"` after `"1.0"`) — **never remove or rename an existing
   member**, or rows stamped to it lose a valid version stamp.
2. Move the `MatrixVersion` column's `default:` to the new version.
3. Update the version literal in *both* matrix formulas'
   `[MatrixVersion]<>"..."` guards, and update the matrix cells themselves
   (the `CHOOSE(...)` argument lists) to the revised ratings and scores.
   Update the ASCII matrix table in the comment above `calculated_formulas`
   to match — it is what the next person reads before touching a cell.
4. Bump `schema_version` in `release.yaml`, rebuild, redeploy.

After that redeploy: rows still stamped to the old version show a blank
`ResidualRiskRating` and `RiskScore` — not the old rating, not a rating
computed from the new matrix, blank — because their `MatrixVersion` value
no longer matches either guard. That blank is a to-do list, not an error:
each owner reassesses their risk under the new matrix and updates
`MatrixVersion` on that row to the new value, which is the only thing that
makes the rating reappear. Nothing does this in bulk; it is deliberately a
per-row human act, because a matrix revision is exactly the moment ratings
should be looked at again, not silently carried forward.

Export the register to Excel before any matrix change — that snapshot
preserves the ratings as they stood immediately before the revision.

## Enforcement boundary

Two rules protect this register's data quality, and they sit in different
places for a specific reason.

- **The Tolerate/Tolerance End Date rule is enforced by SharePoint.** The
  list-level validation formula in `mapping.yaml` refuses to save a row
  where `RiskResponse` is `Tolerate` and `ToleranceEndDate` is empty. This
  works because both columns are plain Choice/Date columns a validation
  formula can read.
- **The Closure Statement requirement is *not* enforced by SharePoint, and
  cannot be.** `ClosureStatement` is a rich-text column, and SharePoint's
  list and column validation formulas cannot reference rich-text columns
  at all — there is no formula that can check whether it is empty. Closing
  a risk without a real closure statement is therefore a **process
  failure the register cannot catch by itself**: an RR Risk Manager reads
  the statement before moving Status to Closed, and that reading is the
  actual control, not a formula standing in for one.

Do not add columns hoping to route around this: the same rich-text
limitation applies to `Detail`, `Controls` and `Treatment` — none of them
can be referenced by a validation formula either.

## Sealed columns and deletion protection

This register uses the fleet-standard hardening declared in
`mapping.yaml`: `seal_columns: true` blocks UI schema edits and deletion of
every deployed column, even for site admins (a display-name rename still
gets through — that is drift, reverted and reported at the next
re-paste), and `prevent_list_deletion: true` removes "Delete this list"
from `RR_Risk` for everyone. Both are friction and tamper-evidence, not
enforcement against a determined site collection admin working through the
API — see "Hardening and drift detection" in
[`templates/README.md`](../../README.md). The deploy script unseals for
its own run and re-seals afterwards; nobody else should need to.

## Data-quality rules

1. `RiskOwner` and `Category` are mandatory on every row — SharePoint
   refuses to save without them.
2. Consequence is "worst credible", agreed at review — not re-argued
   weekly.
3. Closed risks keep their history; a recurrence is a new row, with
   `SourceReference` or `Detail` naming the old one.

### What the register enforces, and what it cannot

Four rules are enforced at save. Three are cross-column and therefore
share a single message, because SharePoint gives a list one validation
formula; the fourth reads only its own column and so keeps its own.

| Rule | Where |
|---|---|
| A Tolerate response carries a Tolerance End Date | list (shared message) |
| A risk past Provisional has both Likelihood and Consequence | list (shared message) |
| A Closed risk has controls rated *All reasonable controls in place* or better | list (shared message) |
| Last Reviewed Date is never in the future | column (own message) |

**Two things remain governance checks, and both are platform limits rather
than choices.**

*A Closed risk carries a real Closure Statement.* Validation formulas
cannot read multi-line columns — plain or rich text alike, so retyping it
as plain text would not help. An RR Risk Manager reads it before the
status moves.

*Residual is at or below target at closure.* `LevelsAboveTarget` is a
calculated column, and validation formulas cannot read those either.

The compensating control is the **Closed risks** view, which carries
`LevelsAboveTarget` for exactly this purpose: anything above 0 there was
closed above appetite, and closure review is where that gets caught. It is
*not* the **Above target** view, which filters out closed risks — a risk
wrongly closed while above target leaves that view at the moment it most
needs watching, so a control resting on it would be looking away precisely
when the failure happens.

Enforcing the third rule at all is new. The `OverallControlEffectiveness`
column description has always stated it; until it was declared, nothing
checked it.

## Lifecycle

Export before decommissioning. Never run `rollback.js` against a populated
register — it is for a failed first provision on an empty site, and for
clearing demo data seeded with `--seed`.
