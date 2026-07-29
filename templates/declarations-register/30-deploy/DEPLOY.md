# Deploying the declarations register (administrator)

Shared procedure: [`templates/README.md`](../../README.md) with
`<name> = declarations-register`. Run order: **assess** the target site
(paste `build/assess.js`, read-only; the verdict must be COMPATIBLE or an
accepted DEGRADED) → **review** `build/deploy-manifest.md` (must show 0
validation errors) → **paste** `build/deploy.js` from a Site Owner's
console → **verify** against the checklist below. Template-specific notes
follow.

## Before you build

- [ ] `DR_` prefix free on the target site.
- [ ] Enums match your code of conduct's categories. `Status` and
      `Decision` are both colour-mapped in `mapping.yaml`, so a renamed
      member strands old rows *and* silently loses its colour.
- [ ] **Visibility decision made** (see the note in `mapping.yaml`): open
      register (default — all site members read) vs confidential register
      (scope site membership to the compliance function). Record the choice
      in `50-govern/GOVERNANCE.md`.
- [ ] Gift value thresholds agreed and written into governance — **and
      then set `EstimatedValue`'s data-bar `max` in `mapping.yaml` to
      match.** It ships at 200, keyed to the threshold ladder this template
      ships with (token under $50, manager decides to $150, integrity owner
      above that). A bar scaled to somebody else's ladder means nothing.
- [ ] **Decide your review horizon before first deploy.** The *Reviews
      due* view on `DR_Interest` filters `ReviewDate ≤ today+30`, matching
      the monthly cadence in governance. Change the `today+30` in
      `mapping.yaml` now if yours differs.
- [ ] The headers show `Interest: <title>` and `Offer: <title>` on saved
      rows, and `New declaration` before the title is filled in, updating
      live as it is typed.

## Optional: the seeded demonstration build

The status colours, the value bar and every declared view are invisible on
two empty lists. To see them working, rebuild with `--seed`:

```bash
dbml-sharepoint build \
  --schema templates/declarations-register/10-design/schema.dbml \
  --mapping templates/declarations-register/20-configure/mapping.yaml \
  --release templates/declarations-register/20-configure/release.yaml \
  --site-url https://yourtenant.sharepoint.com/sites/your-site \
  --site-role default \
  --seed \
  --out ./build
```

That bundle contains an extra file, `demo-data.js`. Paste `deploy.js`
first, then `demo-data.js`, from the same bundle. It creates five interests
— one per status, including a managed conflict whose review falls inside
the window — and five offers, one per decision, with the **same offeror
appearing twice** so that *By offeror* shows the repeat pattern the annual
report is looking for.

**Delete the demo rows before staff start declaring.** Every demo Title
begins with `[DEMO] `, so they are obvious in every view, they are matched
by Title on re-paste (running it twice never duplicates), and `rollback.js`
treats a list whose rows are *all* demo-marked as demo-only content. A demo
declaration left in a live register is a fabricated record in an evidential
list, which is worse here than almost anywhere else in the library.

## After the paste — verification checklist

- [ ] `DR_Interest` and `DR_GiftBenefit` both exist; custom level
      **DR Declare Only** exists.
- [ ] The two lists are fully independent — no lookups between them.
- [ ] **Interest** shows five declared views: **Live interests** (the
      default), **My interests**, **Awaiting assessment**, **Reviews due**,
      **Ceased**. **GiftBenefit** shows four: **Last 12 months** (the
      default), **Pending decisions**, **Annual disclosure**,
      **By offeror**. If you seeded, none of them is empty. The generated
      **All Items** recovery views are hidden from the modern view bar
      because both lists have an authored default.
- [ ] **My interests** shows only your own rows, and shows a different set
      to each person who opens it. It filters on the current user through
      CAML's own `<UserID/>`, which is the only way a person column can be
      compared in a view at all — sign in as a second person to confirm.
- [ ] **Awaiting assessment** is new; it was not in the old *Recommended
      views* table. Governance sets a ten-business-day assessment SLA and
      there was no queue to read it from. Oldest first, because the oldest
      unassessed declaration is the one closest to breaching it.
- [ ] **Last 12 months** and **Annual disclosure** are both **rolling**
      365-day windows, not a calendar or financial year. CAML has no
      calendar-period predicate; the two readings differ on the first day
      of your year and anyone reconciling a disclosure pack will notice.
      They share a window and differ in sort — what happened when, versus
      what was worth most.
- [ ] **Pending decisions** has **no** date window, deliberately. A
      pending decision from fourteen months ago is worse than one from last
      week, not less relevant.
- [ ] List Settings → Indexed columns shows `Status`, `DeclaredBy` and
      `ReviewDate` on Interest, and `Decision`, `OfferedTo` and
      `OfferedDate` on GiftBenefit. The build manifest lists the same six.
- [ ] **As an ordinary Member, this is the test that matters.** You can
      submit a declaration to each list but cannot edit it afterwards —
      and on the New form you never see the assessment fields at all. On
      `DR_Interest`, **Status**, **Management plan**, **Review date** and
      **Ceased date** are absent. On `DR_GiftBenefit`, **Decision** and
      **Decided by** are absent. Governance says the declarer never
      assesses their own declaration and the person offered a gift never
      decides their own gift; this is what makes that structural rather
      than cultural.
- [ ] As a Coordinator: you can assess. On an existing interest, set
      **Status** to *Assessed - managed* and **Management plan** and
      **Review date** both appear; set it to *Ceased* and **Ceased date**
      appears. On an existing offer, move **Decision** off *Pending
      decision* and **Decided by** appears. Changing back hides them again
      while keeping whatever was typed — SharePoint has no mechanism to
      clear a hidden field.
- [ ] `DR_Interest` carries **two** chained save rules sharing one
      message, because SharePoint gives a list a single validation formula.
      Try each: *Assessed - managed* with **Review date** empty; *Ceased*
      with **Ceased date** empty. Both are refused, and both show the same
      message naming both checks.
- [ ] `DR_GiftBenefit` carries **no** list rule. That is not an omission —
      see below.
- [ ] Four per-column save rules, each with its own message: a future
      **Declared date** or **Ceased date** on Interest, a future
      **Offered date** or a negative **Estimated value** on GiftBenefit.
- [ ] `ReviewDate` escalates to the severe treatment once it is past, and
      the escalation is suppressed on a **Ceased** row.
- [ ] Populate **DR Compliance Coordinators**; delete the test rows.
- [ ] Even as an owner: changing a deployed column's type, choices or
      settings is refused (sealed) and List settings offers no "Delete
      this list"; a display-name rename is still possible — it is
      drift, reverted and reported at the next re-paste.

## What is not enforced at save

- **A decided gift needs a `DecisionBy`.** This is the one cross-column
  rule `DR_GiftBenefit` wants and it **cannot be written**: SharePoint
  validation formulas cannot reference a person column at all, so the build
  refuses the rule rather than emitting a formula the platform would reject
  at save. It stays a governance check, and *Annual disclosure* shows
  **Decided by** so a blank one is visible in the report that matters most.
- **The management plan on a managed interest.** `ManagementPlan` is rich
  text, which a validation formula cannot reference either. The date half
  of that governance rule *is* enforced; the plan half is what the *Reviews
  due* view shows the column for.
- **Declaring at all.** No register can require a declaration nobody makes.
  The annual attestation is the control, and *My interests* is what makes
  it a two-minute read rather than a project.

## Redeploying

Bump `schema_version`, rebuild, re-paste. Existing rows are untouched;
drifted settings are reconciled, and declared views are reconciled to the
declaration — a view retitled by hand comes back under its declared title.
