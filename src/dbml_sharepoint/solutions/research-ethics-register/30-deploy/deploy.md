# Deploying the research ethics register (administrator)

Shared procedure: [`templates/README.md`](../../README.md) with
`<name> = research-ethics-register`. Run order: **assess** the target site
(paste `build/assess.js.txt`, read-only) → **review**
`build/deploy-manifest.md` (must show 0 validation errors) → **paste**
`build/deploy.js.txt` from a Site Owner's console → **verify** against the
checklist below. Template-specific notes follow.

## Before you build

- [ ] `RG_` prefix free on the target site.
- [ ] **The two gates are how your service actually works.** This register
      assumes ethics approval comes from an *external* committee and site
      authorisation from *your* Chief Executive or delegate on your research
      governance officer's assessment. If your service holds its own HREC,
      the ethics half still fits but `ReviewingHREC` becomes your own
      committee and the two gates stop being independent in practice — worth
      a conversation before you deploy rather than after.
- [ ] **Fit the three jurisdiction-specific enums** in
      `10-design/schema.dbml`. `ethics_pathway`, `ethics_status` and
      `authorisation_status` are the ones that differ most between states and
      between committees. Edit them **now**: renaming a choice after first
      deploy strands every existing row on the old value.
- [ ] **Decide whether a quality-improvement activity needs site
      authorisation at your service.** As shipped, the save rule permits a
      project to be authorised when `EthicsStatus` is *Approved* **or**
      *Ethics review not required*, which is what lets a QI activity through
      the gate honestly. Whether such an activity needs authorising at all is
      your policy, not the template's.
- [ ] Decide your two windows. Approvals surface at **today+90** and reports
      at **today+60**; both numbers live once each, in their view, and both
      view titles are deliberately silent about them so changing one does not
      leave a title lying.
- [ ] **Privacy check**: site membership reviewed. The register holds no
      participant data, but it does hold who is investigating what and the
      conditions a committee attached to their project. The default is
      all-staff read; make the decision deliberately and record it in
      `50-govern/governance.md`.
- [ ] You know who forms **RG Research Governance**.
- [ ] Each header shows `Project: <title>` / `Amendment: <title>` /
      `Report: <title>` on a saved row and `New project` / `New amendment` /
      `New report` before the title is typed, updating live.

**Expected manifest findings: none.** This template builds at 0 errors and 0
warnings. Anything at all is worth reading.

### On the guide link in the form headers — there isn't one, deliberately

The family standard permits a themed link to an external document in a form
header. This register does not carry one, for the same reason
`credentialing-register` does not: the document it defers to is *your*
research governance procedure and *your* reviewing committee's terms of
reference — a class of document, not one the template can name. The only link
shippable from here is a `REPLACE-WITH-...` placeholder, and a dead link in
the header of the form where somebody transcribes a committee decision
implies the authority is one click away when it is not.

**Adding a real one is two lines** in
`20-configure/formatting/project-form-header.json`, beside the strapline:

```json
{
  "elmType": "a",
  "attributes": {
    "href": "https://yourtenant.sharepoint.com/sites/governance/research-governance-procedure.aspx",
    "target": "_blank",
    "class": "ms-fontColor-themePrimary ms-fontSize-12"
  },
  "txtContent": "Research governance procedure"
}
```

Use an **absolute `https://` address**. SharePoint's formatter emits only
`http`, `https`, `mailto` and `tel` links, so a site-relative path is not a
valid substitution — it renders as text that looks like a link and does
nothing.

## Optional: the seeded demonstration build

The readiness pill, the row wash and the two grouped views are invisible on
empty lists. To see them working, rebuild with `--seed`:

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
first, then `demo-data.js.txt`, from the same bundle. It creates six projects,
five amendments and five reports.

**One demo project is deliberately wrong.** *Falls prevention bundle
evaluation* is ethics-approved, its site-specific assessment is still under
governance review, its approval conditions are outstanding — and its stage
says it is already underway. That is the state this register exists to catch,
it is the row the wash fires on, and its Governance Notes say so. Do not
"fix" it before you have seen it render.

**Delete the demo rows before active use.** Every demo Title begins with
`[DEMO] `, they are matched by Title on re-paste (running it twice never
duplicates), and `rollback.js.txt` treats a list whose rows are *all*
demo-marked as demo-only content. Do not seed a site that already holds real
projects.

## After the paste — verification checklist

- [ ] `RG_Project`, `RG_Amendment` and `RG_ProgressReport` exist (Project
      first — both child lists look it up).
- [ ] All five **Project** views appear: **Current projects** (the default),
      **Approved, not authorised**, **Approvals expiring**, **Conditions
      outstanding**, **Closed projects**.
- [ ] All four **Amendment** views appear: **By project** (the default,
      grouped by the Project lookup and collapsed), **With the HREC**,
      **Approved, not cleared locally**, **Decided**.
- [ ] All five **ProgressReport** views appear: **Outstanding reports** (the
      default), **By project** (grouped and collapsed), **Due in 60 days**,
      **Information requested**, **Filed**. If you seeded, none of the
      fourteen is empty. The generated **All Items** recovery view is hidden
      from the modern view bar on all three lists, because each has an
      authored default.
- [ ] **The two gates read as two things.** On *Current projects*, **Ethics
      Status** and **Site Authorisation Status** sit side by side with **Site
      Readiness** beside them. Change one and watch Site Readiness change and
      the other stay put — that is the whole design in one interaction.
- [ ] **Site Readiness renders in colour**, not as bare text. If it renders
      plain, the `calculated: true` flag has been lost from its
      `column_formatting` entry: a calculated text value arrives prefixed
      `string;#` and the map will not match without it.
- [ ] In *Current projects*, the **Falls prevention bundle evaluation** row
      carries a dusty-rose wash across its whole width. That is the one
      row-level signal on this register — a project whose stage says it has
      started, with no site authorisation. Set its Site Authorisation Status
      to **Authorised** and the wash goes. Nothing else competes with it.
- [ ] The Project form shows **The project**, **Review pathway**, **Ethics
      decision**, **Site authorisation**, **Oversight** and **System**. Two
      separate approval sections, deliberately. Every column sits in one of
      them.
- [ ] On a project, set **Conditions Status** to *Outstanding* and
      **Approval Conditions** appears; set it back to *None* and it goes.
- [ ] On an amendment, choose **Site Impact** = *No local action needed* and
      **Site Cleared Date** disappears; choose either other value and it
      returns.
- [ ] An **Ethics Approval Expiry** or **Next Report Due** in the past
      renders with the severe treatment and a warning icon. Move that
      project's stage to **Completed** and both go plain — at a terminal
      stage they are history rather than deadlines.
- [ ] Save rules, all eight:
      - A **Submitted Date**, **Ethics Decision Date** or **Authorisation
        Date** in the future is refused on Project, each with its own
        message.
      - Setting **Site Authorisation Status** to *Authorised* while **Ethics
        Status** is anything other than *Approved* or *Ethics review not
        required* is refused, with the list's message. **This is the domain
        rule**: a site authorisation is given against evidence of ethics
        clearance.
      - A **Submitted Date** in the future is refused on Amendment and on
        ProgressReport.
      - An amendment set to **Approved** with no **Decision Date** is
        refused.
      - A report set to **Submitted** or **Acknowledged** with no
        **Submitted Date** is refused.
- [ ] Create a test project; add an amendment and a report against it (the
      Project lookup offers the row); confirm both grouped *By project* views
      show them under it.
- [ ] As an ordinary Member: read-only.
- [ ] **Load the live projects** — the register is only trustworthy complete.
      Every project currently approved or in review, with both gates as they
      actually stand today, its approval expiry, and its next report date.
      This is the project; budget real time for it, and expect to discover at
      least one project whose authorisation nobody can find.
- [ ] Populate **RG Research Governance**; delete the test rows.
- [ ] Even as an owner: changing a deployed column's type, choices or
      settings is refused (sealed) and List settings offers no "Delete this
      list"; a display-name rename is still possible — it is drift, reverted
      and reported at the next re-paste.

### "Per project", and what ships instead

Both child lists would naturally want a view *filtered to one project* — the
amendment history, the reporting file. A static view cannot filter to one
parent record, so the choices were N views that rot as projects are added, or
one grouped view that does not.

What ships on each is **By project**: grouped by the Project lookup,
collapsed, and deliberately **unfiltered**. Opening a project's group *is*
its amendment history or its reporting file, and the refused, withdrawn and
acknowledged rows belong in it.

### What the register cannot compute, and what covers it

`SiteReadiness` is a SharePoint calculated column, and a calculated column
may not reference `[Today]` — the build refuses one that does. So **Site
Readiness does not know that an approval expired yesterday**. It keeps saying
*Ready to start here* until somebody moves **Ethics Status** to *Expired*.

Two live surfaces cover the gap, and neither is a stored number: the
*Approvals expiring* view filters at query time, and the red on **Ethics
Approval Expiry** is computed in the browser at render time. The third cover
is a person — the monthly expiry sweep in `50-govern/governance.md`, which is
a named duty for exactly this reason.

## Redeploying

Bump `schema_version`, rebuild, re-paste. Rows untouched; views, forms,
formatting and save rules reconciled to the declaration.
