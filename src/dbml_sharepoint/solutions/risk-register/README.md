# Risk register

A single-list organisational risk register with a self-rating 5x5 matrix:
pick **Likelihood** and **Consequence**, and SharePoint calculates
**ResidualRiskRating** (Low/Medium/High/Extreme) and a 1-25 **RiskScore**.
There is nowhere to type a rating that disagrees with the matrix, because
the rating is never typed at all. One list: `RR_Risk`.

**The value case.** Most risk registers die in spreadsheets: one owner, one
laptop, ratings hand-typed and quietly inconsistent with the matrix on the
wall. This one is shared, versioned, and the rating and score are enforced
by formula, not by hoping. It fits any function (strategic, operational,
clinical, project), which is what makes it a whole-of-business quick win.

**Title, plus 21 more columns, at a glance:**

| Group | Columns |
| --- | --- |
| Describe | `Detail`, `Category` |
| Assess | `Likelihood`, `Consequence`, `TargetRiskRating`, `LastReviewedDate` |
| Respond | `RiskResponse`, `ToleranceEndDate`, `Controls`, `Treatment`, `OverallControlEffectiveness`, `ClosureStatement` |
| Govern | `RiskOwner`, `RiskSponsor`, `Status`, `NextReviewDue` *(calculated)*, `SourceReference` |
| System | `ResidualRiskRating` *(calculated)*, `RiskScore` *(calculated)*, `LevelsAboveTarget` *(calculated)*, `MatrixVersion` |

Four columns are calculated and read-only. The three matrix outputs
(`ResidualRiskRating`, `RiskScore` and `LevelsAboveTarget`) sit at the bottom
of Edit and Display forms in the **System** section rather than interrupting
the assessment inputs. `NextReviewDue` stays in **Governance**, where its
date is useful during review. `MatrixVersion` is off the New form (it stamps
itself) but remains editable in **System** on existing rows so the
matrix-revision procedure in `50-govern/governance.md` can re-stamp them.
The form groups all columns into the same sections as the table above.

**Five declared views**, deployed with the paste, nothing to build by
hand: *Open* (the default), *Review due*, *Above target*, *Tolerance due*,
*Closed*. The shorter labels keep more views visible in the modern toolbar.

**Five supported SharePoint indexes** are declared in `schema.dbml`:
`Status`, `Category`, `RiskResponse`, `ToleranceEndDate` and
`LastReviewedDate`. SharePoint cannot index the calculated `RiskScore`,
`ResidualRiskRating`, `LevelsAboveTarget` or `NextReviewDue` columns, so the
views driven by those calculations are not guaranteed to scale beyond the
list-view threshold without redesigning those values as persisted fields.

**Work the folders in order:**

| Step | Folder | You |
| --- | --- | --- |
| 1 | `10-design/` | Fit `Category` to your risk taxonomy |
| 2 | `20-configure/` | Prefix; **the matrix lives here**, edit with care |
| 3 | `30-deploy/` | Administrator: build, paste, verify the matrix calculates |
| 4 | `40-adopt/` | Risk owners' guide: raising, rating and reviewing risks |
| 5 | `50-govern/` | Matrix change control, review cadence, the Status/RiskResponse split |

**Customisation points:** the `Category` enum; the matrix cells in
`mapping.yaml` (read the change-control section of `50-govern/governance.md`
first: changing a cell recalculates every existing row); and the strapline
in `20-configure/formatting/risk-form-header.json`, which tells a risk owner
the one thing that makes the form work. The header carries no link: a
placeholder URL is a dead link on every form until somebody remembers to
replace it, so point at your risk-process document from the column
descriptions instead.

**Demo data.** Build with `--seed` and the bundle gains a `demo-data.js.txt`
that pastes six `[DEMO]`-titled rows (one per rating band, a Tolerate risk
inside its tolerance window, and a Closed risk with a closure statement), so
every view, colour band and score bar renders on a first look. See
`30-deploy/deploy.md`.
