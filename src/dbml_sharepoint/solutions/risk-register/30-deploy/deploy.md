# Deploying the risk register (administrator)

Shared procedure: [`templates/README.md`](../../README.md) with
`<name> = risk-register`. Run order: **assess** the target site (paste
`build/assess.js.txt`, read-only; the verdict must be COMPATIBLE or an accepted
DEGRADED) → **review** `build/deploy-manifest.md` (must show 0 validation
errors) → **paste** `build/deploy.js.txt` from a Site Owner's console → **verify**
against the checklist below. Template-specific notes follow.

## Before you build

- [ ] `RR_` prefix free on the target site.
- [ ] `Category` enum matches your risk taxonomy.
- [ ] **Decide whether a Risk Sponsor is mandatory.** `RiskSponsor` ships
      optional. The two options and their costs are set out at the column
      in `10-design/schema.dbml`; requiring one is adding `[not null]`
      there. Decide **before first deploy** — flipping it later re-validates
      every existing row, so a register that has been running without
      sponsors will refuse to save any of them until each is filled in.
      There is no middle setting: SharePoint validation formulas cannot
      read person columns, so "required only once it leaves Provisional"
      is not expressible.
- [ ] If your organisation has its OWN risk matrix, encode it in
      `mapping.yaml` **now**, before first deploy — the comment above
      `calculated_formulas` shows the cell layout; keep the DBML
      Likelihood/Consequence enums in the same order the formulas index
      them.
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
  --schema 10-design/schema.dbml \
  --mapping 20-configure/mapping.yaml \
  --release 20-configure/release.yaml \
  --site-url https://yourtenant.sharepoint.com/sites/your-site \
  --site-role default \
  --seed \
  --out ./build
```

That bundle contains an extra file, `demo-data.js.txt`. Paste `deploy.js.txt` first,
then `demo-data.js.txt`, from the same bundle. It creates six rows — one per
rating band (Low/Medium/High/Extreme), a Tolerate risk inside its
tolerance-expiry window, and a Closed risk carrying a closure statement —
enough that every declared view and every colour band has content.

**Delete the demo rows before active use.** Every demo Title begins with
`[DEMO] `, so they are obvious in every view, they are matched by Title on
re-paste (running it twice never duplicates), and `rollback.js.txt` treats a
list whose rows are *all* demo-marked as demo-only content. Do not seed a
site that already holds real risks.

## After the paste — verification checklist

- [ ] `RR_Risk` exists and all five declared views appear: **Open** (the
      default), **Review due**, **Above target**, **Tolerance due**,
      **Closed**. If you seeded, none of them
      is empty. The generated **All Items** recovery view is hidden from the
      modern view bar because this template has an authored default.
- [ ] If upgrading a site that previously deployed the longer view titles,
      delete **Open by score**, **Reviews due**, **Tolerance expiring** and
      **Closed risks** after confirming the short replacements. This clean-cut
      template does not adopt or delete those legacy views.
- [ ] List Settings → Indexed columns shows `Status`, `Category`,
      `RiskResponse`, `ToleranceEndDate` and `LastReviewedDate`. The build
      manifest lists the same five under **indexed columns**.
- [ ] Matrix spot-checks on a test risk:
      - Rare + Minor → **Low / 1**
      - Unlikely + Substantial → **Medium / 11**
      - Very Likely + Business Critical → **Extreme / 24**
      - Clear Likelihood → `ResidualRiskRating` and `RiskScore` both go
        **blank** (unrated is visible, not defaulted).
- [ ] The New form shows **Describe the risk**, **Assess the risk**,
      **Response and controls** and **Governance**, each holding the fields
      named in `20-configure/formatting/risk-form-body.json`. **System** is
      last and holds the three calculated matrix outputs plus
      `MatrixVersion`; it does not interrupt the assessment inputs.
- [ ] `MatrixVersion` is absent from the New form and present on the Edit
      and Display forms — it is the audit stamp for which matrix version
      rated the row, not something a risk owner sets at creation, but it
      must stay editable so an owner can re-stamp it on an old row during
      the matrix-revision procedure in `50-govern/governance.md`.
- [ ] On Edit and Display, `ResidualRiskRating`, `RiskScore` and
      `LevelsAboveTarget` appear read-only under **System**. `NextReviewDue`
      appears read-only under **Governance**. None can be typed over.
- [ ] The form reacts as you fill it in. On a New form, `ToleranceEndDate`
      and `ClosureStatement` are both absent. Set `RiskResponse` to
      **Tolerate** and the date appears; switch to **Manage** and it
      disappears again, keeping whatever was typed. `LastReviewedDate` is
      absent on New and present on Edit.
- [ ] The list carries **three** chained save rules sharing one message,
      because SharePoint gives a list a single validation formula. Try each:
      set `RiskResponse` to **Tolerate** with `ToleranceEndDate` empty; move
      `Status` off **Provisional** with `Likelihood` or `Consequence` blank;
      set `Status` to **Closed** with `OverallControlEffectiveness` at
      *Partially effective* or worse. All three are refused, all three show
      the same message naming all three checks — that is the platform
      limit, not a defect, and it is why a rule that reads only its own
      column belongs in `column_validation` where it keeps its own message.
      For Tolerate, note the date field is on screen when the refusal
      fires: a rejection naming a field the author cannot see is what the
      visibility rule exists to prevent.
- [ ] `LastReviewedDate` refuses a blank through its required-field check and
      refuses a future date with its own validation message.
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
`50-govern/governance.md` (export a snapshot first, then the
`MatrixVersion` append-and-re-version steps) before touching any cell.

## Enterprise reporting access

The deploy declares the `dbml Enterprise Readers` site group — shared with every
other family deployed to the site — and grants it `Read` on every list in this
family. The group starts empty only if no family has deployed to the site yet;
it gains a member when any family's build is run with `--enterprise-reader
<account>`, which enrols exactly that one account and nothing else.
`rollback.js.txt` does not remove it: rollback deletes lists, not site groups
or role assignments, so the group and any account enrolled in it survive a
rollback.

A later build that omits the flag does not put the group back to empty:
enrolment only runs when `--enterprise-reader` is given, so an account enrolled
by an earlier build — of this family or any other sharing the site — keeps its
membership and its `Read` grant on every list it was declared against. Removing
it is manual — clear it in Site permissions > Groups.

If the group already holds anyone other than that account, the deploy
**aborts before enrolling** and removes nobody. Before you clear anyone out,
check who it is: the group is shared by every family on this site, so the
unexpected member is most likely **another family's reporting account**, and
removing it silently breaks that family's reporting. Agree one reader account
for the site and rebuild with that address, or rebuild without the flag. Only
clear the group in Site permissions > Groups once you know nothing else needs
the account.

On one Microsoft 365 group-connected Team Site (measured 2026-08-11) the
enrolled account ends up with the built-in `Read` on each list and
`Use Remote Interfaces` intact at web scope. Publishing sites — where
lockdown mode is on by default — and the reporting client's own list
enumeration are still unverified, so the end-to-end path (Power BI or any
other API client) is not yet proven. See the danger block in the mapping
reference's Security section.
