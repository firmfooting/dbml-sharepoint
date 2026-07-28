# Deploying the risk register (administrator)

Shared procedure: [`templates/README.md`](../../README.md) with
`<name> = risk-register`. Run order: **assess** the target site (paste
`build/assess.js`, read-only; the verdict must be COMPATIBLE or an accepted
DEGRADED) → **review** `build/deploy-manifest.md` (must show 0 validation
errors) → **paste** `build/deploy.js` from a Site Owner's console → **verify**
against the checklist below. Template-specific notes follow.

## Before you build

- [ ] `RR_` prefix free on the target site.
- [ ] `Category` enum matches your risk taxonomy.
- [ ] If your organisation has its OWN risk matrix, encode it in
      `mapping.yaml` **now**, before first deploy — the comment above
      `calculated_formulas` shows the cell layout; keep the DBML
      Likelihood/Consequence enums in the same order the formulas index
      them.
- [ ] `20-configure/formatting/risk-form-header.json` carries a literal
      placeholder, `https://REPLACE-WITH-PROJECT-RISK-PROCESS-URL`, as the
      "Project risk process guide" link shown on every New, Edit **and
      Display** form — the header formatter applies to all three.
      **Set it to your organisation's real risk-process document, or delete
      that link element entirely, before you deploy** — every form you
      hand to a risk owner would otherwise carry a dead link.
      Use an **absolute** `https://` address: SharePoint's formatter only
      emits `http://`, `https://`, `mailto:` and `tel:` links, so a
      site-relative path is not a valid substitution here.
- [ ] The header shows `Risk: <title>` on a saved risk and `New risk`
      before the title is filled in, updating live as it is typed. If you
      add another `[$FieldName]` reference, note that a **calculated**
      column always resolves empty in a form header — `ResidualRiskRating`,
      `RiskScore`, `LevelsAboveTarget` and `NextReviewDue` will show
      nothing there, with no error. Their values reach the form through
      their own `column_formatting`, in the body sections.

## Optional: the seeded demonstration build

The matrix, the row wash on an Extreme risk, the score bar and every
declared view are invisible on an empty list. To see them working, rebuild
with `--seed`:

```bash
dbml-sharepoint build \
  --schema templates/risk-register/10-design/schema.dbml \
  --mapping templates/risk-register/20-configure/mapping.yaml \
  --release templates/risk-register/20-configure/release.yaml \
  --site-url https://yourtenant.sharepoint.com/sites/your-site \
  --site-role default \
  --seed \
  --out ./build
```

That bundle contains an extra file, `demo-data.js`. Paste `deploy.js` first,
then `demo-data.js`, from the same bundle. It creates six rows — one per
rating band (Low/Medium/High/Extreme), a Tolerate risk inside its
tolerance-expiry window, and a Closed risk carrying a closure statement —
enough that every declared view and every colour band has content.

**Delete the demo rows before active use.** Every demo Title begins with
`[DEMO] `, so they are obvious in every view, they are matched by Title on
re-paste (running it twice never duplicates), and `rollback.js` treats a
list whose rows are *all* demo-marked as demo-only content. Do not seed a
site that already holds real risks.

## After the paste — verification checklist

- [ ] `RR_Risk` exists and all five declared views appear: **Open by
      score** (the default), **Reviews due**, **Above target**,
      **Tolerance expiring**, **Closed risks**. If you seeded, none of them
      is empty.
- [ ] Matrix spot-checks on a test risk:
      - Rare + Minor → **Low / 1**
      - Unlikely + Substantial → **Medium / 11**
      - Very Likely + Business Critical → **Extreme / 24**
      - Clear Likelihood → `ResidualRiskRating` and `RiskScore` both go
        **blank** (unrated is visible, not defaulted).
- [ ] The New form shows four sections: **Describe the risk**, **Assess the
      risk**, **Response and controls**, **Governance**. **System** holds
      only `MatrixVersion`, which is off the New form, so that section does
      not appear there; it shows on Edit and Display.
- [ ] `MatrixVersion` is absent from the New form and present on the Edit
      and Display forms — it is the audit stamp for which matrix version
      rated the row, not something a risk owner sets at creation, but it
      must stay editable so an owner can re-stamp it on an old row during
      the matrix-revision procedure in `50-govern/GOVERNANCE.md`.
- [ ] `ResidualRiskRating`, `RiskScore`, `LevelsAboveTarget` and
      `NextReviewDue` are calculated and never appear on the New or Edit
      form either.
- [ ] The form reacts as you fill it in. On a New form, `ToleranceEndDate`
      and `ClosureStatement` are both absent. Set `RiskResponse` to
      **Tolerate** and the date appears; switch to **Manage** and it
      disappears again, keeping whatever was typed. `LastReviewedDate` is
      absent on New and present on Edit.
- [ ] With `RiskResponse` on **Tolerate**, save with `ToleranceEndDate`
      empty. Expected refusal: *"A Tolerate response is always for a set
      period: record the Tolerance End Date, and have the Risk Sponsor
      reassess before it."* The field is on screen when this fires — that
      pairing is the point of the visibility rule, and a refusal naming a
      field the author cannot see is the failure it exists to prevent.
- [ ] On an existing risk, set `Status` to **Closed** and confirm
      `ClosureStatement` appears.
- [ ] As an ordinary Member: read-only. As **RR Risk Managers**: Contribute.
- [ ] Populate **RR Risk Managers**; delete the test risk.
- [ ] Even as an owner: changing a deployed column's type, choices or
      settings is refused (sealed) and List settings offers no "Delete
      this list"; a display-name rename is still possible — it is drift,
      reverted and reported at the next re-paste.

## Redeploying — matrix change warning

A redeploy applies formula changes to the live columns, and SharePoint then
**recalculates every existing row**. That is desirable for a typo fix and
dangerous for a matrix revision — follow the change-control procedure in
`50-govern/GOVERNANCE.md` (export a snapshot first, then the
`MatrixVersion` append-and-re-version steps) before touching any cell.
