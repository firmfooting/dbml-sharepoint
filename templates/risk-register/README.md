# Risk register

A single-list organisational risk register with a self-rating 5×5 matrix:
pick **Likelihood** and **Consequence**, and SharePoint calculates
**ResidualRiskRating** (Low/Medium/High/Extreme) and a 1–25 **RiskScore** —
there is nowhere to type a rating that disagrees with the matrix, because
the rating is never typed at all. One list: `RR_Risk`.

**The value case.** Most risk registers die in spreadsheets: one owner, one
laptop, ratings hand-typed and quietly inconsistent with the matrix on the
wall. This one is shared, versioned, and the rating and score are enforced
by formula, not by hoping. It fits any function — strategic, operational,
clinical, project — which is what makes it a whole-of-business quick win.

**Title, plus 21 more columns, at a glance:**

| Group | Columns |
|---|---|
| Describe | `Detail`, `Category` |
| Assess | `Likelihood`, `Consequence`, `ResidualRiskRating` *(calculated)*, `RiskScore` *(calculated)*, `TargetRiskRating`, `LevelsAboveTarget` *(calculated)*, `MatrixVersion` |
| Respond | `RiskResponse`, `ToleranceEndDate`, `Controls`, `Treatment`, `OverallControlEffectiveness`, `ClosureStatement` |
| Govern | `RiskOwner`, `RiskSponsor`, `Status`, `NextReviewDue` *(calculated)*, `LastReviewedDate`, `SourceReference` |

Four columns are calculated and never appear on the New or Edit form —
`ResidualRiskRating`, `RiskScore`, `LevelsAboveTarget`, `NextReviewDue` —
because a person cannot type over the matrix. `MatrixVersion` is also off
the New form (it stamps itself), but unlike those four it stays on Edit and
Display, in its own fifth, system-only section — a risk owner cannot see it
while raising a risk, but it stays correctable on an existing row, which
the matrix-revision procedure in `50-govern/GOVERNANCE.md` depends on.
Everything else is entered by a person; the form groups them into the same
sections as the table above.

**Five declared views**, deployed with the paste — nothing to build by
hand: *Open by score* (the default), *Reviews due*, *Above target*,
*Tolerance expiring*, *Closed risks*.

**Work the folders in order:**

| Step | Folder | You |
|---|---|---|
| 1 | `10-design/` | Fit `Category` to your risk taxonomy |
| 2 | `20-configure/` | Prefix; **the matrix lives here** — edit with care |
| 3 | `30-deploy/` | Administrator: build, paste, verify the matrix calculates |
| 4 | `40-adopt/` | Risk owners' guide: raising, rating and reviewing risks |
| 5 | `50-govern/` | Matrix change control, review cadence, the Status/RiskResponse split |

**Customisation points:** the `Category` enum; the matrix cells in
`mapping.yaml` (read the change-control section of `50-govern/GOVERNANCE.md`
first — changing a cell recalculates every existing row); the risk-process
link in `20-configure/formatting/risk-form-header.json`, which ships with a
placeholder URL — see `30-deploy/DEPLOY.md`.

**Demo data.** Build with `--seed` and the bundle gains a `demo-data.js`
that pastes six `[DEMO] `-titled rows — one per rating band, a Tolerate risk
inside its tolerance window, and a Closed risk with a closure statement — so
every view, colour band and score bar renders on a first look. See
`30-deploy/DEPLOY.md`.
