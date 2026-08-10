# Deploying the research ethics register, single list (administrator)

Shared procedure: [`templates/README.md`](../../README.md) with
`<name> = research-ethics-register-simple`. Run order: **assess** the target
site (paste `build/assess.js.txt`, read-only; the verdict must be COMPATIBLE
or an accepted DEGRADED) → **review** `build/deploy-manifest.md` (must show 0
validation errors) → **paste** `build/deploy.js.txt` from a Site Owner's
console → **verify** against the checklist below. Template-specific notes
follow.

## Before you build

- [ ] `RG_` prefix free on the target site. Note the multi-list research
      ethics register in this library uses the same prefix and provisions a
      list of the same name — deploy one or the other to a site, or change
      this one's prefix in `20-configure/mapping.yaml`.
- [ ] **Decide the site membership before anything else.** This register is
      read-wide by design: *may this project start here* is a question ward
      managers, department heads and student supervisors all have to answer,
      and a register only the governance office can see is a register nobody
      consults. But site membership **is** the audience, so on a
      whole-of-organisation site that Read grant is organisation-wide. The
      register holds staff professional information and the conditions a
      committee attached to somebody's project. Decide deliberately and
      record the decision in `50-govern/governance.md`.
- [ ] You know who forms **RG Research Governance** — the people who record
      decisions and run the two sweeps.
- [ ] `EthicsPathway` and `authorisation_status` members match your partner
      committee's and your own vocabulary (`10-design/schema.dbml`). Both are
      colour-mapped in `mapping.yaml` and both are named in the readiness
      formula, so a renamed member loses its colour **and** silently changes
      what `SiteReadiness` computes. Rename in three places or in none.
- [ ] **Decide your reporting horizon before first deploy.** The *Reports
      due soon* view filters `NextReportDue ≤ today+60`. Change the `today+60`
      in `mapping.yaml` now if your cycle differs — a view title and a filter
      that disagree is worse than either. The title is deliberately silent
      about the number so that changing it does not leave a title lying.
- [ ] The header shows `Project: <title>` on a saved row and `New project`
      before the title is filled in, updating live as it is typed. It carries
      **no** guide link, deliberately: the document this register defers to is
      your service's research governance procedure and your partner
      committee's terms of reference — a class of document, not one this
      template can name. To add yours, append a child to the strapline block
      in `20-configure/formatting/project-form-header.json` with
      `"elmType": "a"` and an **absolute https** target; a relative URL
      resolves against the form and 404s.

## Optional: the seeded demonstration build

The two-gate colours, the readiness column, the row wash and all six views
are invisible on an empty list. To see them working, rebuild with `--seed`:

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

That bundle contains an extra file, `demo-data.js.txt`. Paste `deploy.js.txt`
first, then `demo-data.js.txt`, from the same bundle. It creates six projects
covering every view and every colour map — including **one that is
deliberately wrong**: the falls-prevention evaluation is marked *Underway*
with its site-specific assessment still under governance review, so the row
is washed pink in *Live projects* and its readiness reads amber. That is the
failure the whole register exists to make visible, shipped as a demo so you
meet it before it is real.

**Delete the demo rows before loading real projects.** Every demo Title
begins with `[DEMO] `, so they are obvious in every view, they are matched by
Title on re-paste (running it twice never duplicates), and `rollback.js.txt`
treats a list whose rows are *all* demo-marked as demo-only content.

## After the paste — verification checklist

- [ ] `RG_Project` exists; `Title`, `Project Type`, `Department`,
      `Principal Investigator`, `Ethics Pathway`, `Ethics Status`,
      `Conditions Status`, `Site Authorisation Status`, `Project Stage` and
      `Amendment Count` are required.
- [ ] All six declared views appear: **Live projects** (the default),
      **Ready to start here**, **Ethics cleared, not authorised**,
      **Response required**, **Reports due soon** and **Archive**. If you
      seeded, none of them is empty. The generated **All Items** recovery
      view is hidden from the modern view bar because this template has an
      authored default.
- [ ] **Live projects is the default, and it is filtered.** That filter is
      the whole reason this register works as one list: closed and
      discontinued projects stay in **Archive** and out of the way, so a
      register five years deep still opens on this year's work. Check that a
      completed demo project is absent from the default and present in
      **Archive**.
- [ ] **The two gates read as two things on the form.** The New form shows
      **The project**, **Review pathway**, **Ethics decision**, **Site
      authorisation**, **Oversight and what is owed** and **System**. Ethics
      decision and Site authorisation are consecutive and separate on
      purpose — each with its own status, its own reference number and its
      own dates.
- [ ] **Site Readiness** is in the **System** section, empty on the New form,
      and fills in on save. On the seeded rows it reads *Ready to start here*
      in green, *Ethics cleared - site authorisation outstanding* in amber,
      and nothing in red — red is reserved for *Site authorised - ethics not
      cleared*, which you can produce by setting a demo project's Ethics
      Status to **Expired** while its authorisation stays *Authorised*.
- [ ] **The row wash fires exactly once.** Only the falls-prevention row is
      washed, and only in *Live projects*: a view formatter can read only the
      columns its view displays, and `Project Stage` and `Site Authorisation
      Status` are both in that view's fields. Drop either from `fields` and
      the wash stops firing with a clean build and no error anywhere.
- [ ] **The save rule holds.** Try to set **Site Authorisation Status** to
      *Authorised* on a project whose **Ethics Status** is *Under review*.
      It is refused, with the message naming why. Then set Ethics Status to
      *Ethics review not required* and try again: it saves. That second half
      is deliberate — a quality activity that correctly never went to a
      committee must not be pushed into recording a fake approval.
- [ ] **The three date rules refuse a future date**, each with its own
      message: Submitted Date, Ethics Decision Date and Authorisation Date.
      They live on their columns rather than on the list precisely so each
      keeps its own message.
- [ ] The form reacts as you fill it in. On a New form, **Approval
      Conditions** is absent while Conditions Status is *None*; choose
      *Outstanding* and it appears. **Completed Date** is absent from the New
      form entirely and appears on Edit once the stage is *Completed* or
      *Discontinued*. Changing back hides the field and keeps whatever was
      typed — SharePoint has no mechanism to clear a hidden field's value.
- [ ] **Ethics Approval Expiry** and **Next Report Due** escalate to the
      severe treatment once past, and stop once the stage is *Completed* or
      *Discontinued*. Note both guard on the **stage** rather than on their
      own status column: an approval expiring under a project that is still
      running must keep shouting even after somebody has flipped Ethics
      Status to *Expired*.
- [ ] List Settings → Indexed columns shows exactly four: `Ethics Status`,
      `Site Authorisation Status`, `Project Stage` and `Next Report Due`.
      The build manifest lists the same four. Every declared view filters on
      one of them, including the OR in *Response required* — an OR is only
      served past the list view threshold when **every** branch is indexed,
      and both of its branches are.
- [ ] As an ordinary Member: read-only.
- [ ] Populate **RG Research Governance**; delete the demo rows.
- [ ] Even as an owner: changing a deployed column's type, choices or
      settings is refused (sealed) and List settings offers no "Delete this
      list"; a display-name rename is still possible — it is drift, reverted
      and reported at the next re-paste.

## What is not enforced at save

Four things this register depends on cannot be enforced by SharePoint, and
they are governance duties in `50-govern/governance.md` rather than silent
gaps:

- **Moving Ethics Status to *Expired* when an approval lapses.** Nothing can
  compute it: a SharePoint calculated column may not reference `[Today]`, so
  `SiteReadiness` cannot know that an approval expired yesterday. The overdue
  colouring on the expiry date and the *Reports due soon* filter are the live
  half; a person closes the loop. This is why "report overdue" is a **view
  filter** in this template and never a calculated column.
- **That Summary, Approval Conditions and Governance Notes say anything
  useful.** SharePoint validation formulas cannot reference a multi-line
  column at all, so there is no formula to write.
- **Anything about Site Investigator.** Validation formulas cannot reference
  a person column either. A blank one is caught in *Ethics cleared, not
  authorised*.
- **That Governance Notes is genuinely append-only.** It is an ordinary
  rich-text column: the deployer sets `AppendOnly` false on every multi-line
  column, so the append discipline is a convention backed by 200 versions of
  list history, not a platform guarantee. Said plainly because a column that
  merely looks append-only is worse than one that does not pretend.

## Redeploying

Bump `schema_version`, rebuild, re-paste. Existing rows are untouched;
drifted settings are reconciled, and declared views are reconciled to the
declaration — a view retitled by hand comes back under its declared title.
Version history is not touched, which matters more here than on most
templates: it is the only record of the amendments this design does not give
rows of their own.
