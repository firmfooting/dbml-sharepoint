# Deploying compliance obligations (administrator)

Shared procedure: [`templates/README.md`](../../README.md) with
`<name> = compliance-obligations`. Run order: **assess** the target site
(paste `build/assess.js`, read-only; the verdict must be COMPATIBLE or an
accepted DEGRADED) → **review** `build/deploy-manifest.md` (must show 0
validation errors) → **paste** `build/deploy.js` from a Site Owner's
console → **verify** against the checklist below. Template-specific notes
follow.

## Before you build

- [ ] `CO_` prefix free on the target site.
- [ ] The obligation-grain guidance in `40-adopt/STAFF-GUIDE.md` read by
      whoever will load the register — grain decided before loading, not
      during.
- [ ] `SourceType` matches your obligation landscape
      (`10-design/schema.dbml`). It is the **first** grouping level of the
      accreditation pack, so its members are the pack's chapter headings;
      and `ComplianceStatus` is colour-mapped in `mapping.yaml`, so a
      renamed member silently loses its colour as well as stranding old
      rows.
- [ ] **Decide your review horizon before first deploy.** The *Reviews
      due* view filters `ReviewDate ≤ today+60`. Change the `today+60` in
      `mapping.yaml` now if your cycle differs — a view title and a filter
      that disagree is worse than either.
- [ ] You know who forms **CO Compliance Coordinators**.
- [ ] The header shows `Obligation: <title>` on a saved row and
      `New obligation` before the title is filled in, updating live as it
      is typed. It carries **no** guide link, deliberately: the standard
      allows one where a template points at a single external document, and
      this register points at a different instrument per row — that is what
      `SourceInstrument` and `EvidenceUrl` are for. A header link here could
      only be a placeholder on the form every obligation owner opens.

## Optional: the seeded demonstration build

The status colours, the overdue review dates and the two-level
accreditation grouping are all invisible on an empty list. To see them
working, rebuild with `--seed`:

```bash
dbml-sharepoint build \
  --schema templates/compliance-obligations/10-design/schema.dbml \
  --mapping templates/compliance-obligations/20-configure/mapping.yaml \
  --release templates/compliance-obligations/20-configure/release.yaml \
  --site-url https://yourtenant.sharepoint.com/sites/your-site \
  --site-role default \
  --seed \
  --out ./build
```

That bundle contains an extra file, `demo-data.js`. Paste `deploy.js`
first, then `demo-data.js`, from the same bundle. It creates five rows —
one per `ComplianceStatus` member, across four source types, with **two
instruments under one type** so that *By source* demonstrates both levels
of its grouping rather than one.

**Delete the demo rows before loading real obligations.** Every demo Title
begins with `[DEMO] `, so they are obvious in every view, they are matched
by Title on re-paste (running it twice never duplicates), and `rollback.js`
treats a list whose rows are *all* demo-marked as demo-only content.

## After the paste — verification checklist

- [ ] `CO_Obligation` exists; `SourceInstrument`, `Owner` and `ReviewDate`
      are required.
- [ ] All five declared views appear: **By owner** (the default),
      **The gap list**, **Not yet assessed**, **Reviews due**,
      **By source**. If you seeded, none of them is empty. The generated
      **All Items** recovery view is hidden from the modern view bar
      because this template has an authored default.
- [ ] **By source** groups on `SourceType` **and then** on
      `SourceInstrument`, both collapsed — the accreditation pack, two
      levels deep. Two is SharePoint's own ceiling, not this tool's.
- [ ] **By owner** is the default. There is no unfiltered "all
      obligations" view and that is deliberate: no row in this register
      ever stops mattering, so an unfiltered list and a grouped-by-owner
      list hold exactly the same rows — grouping is what makes "which of
      these are mine" answerable at a glance. Expand a group to see the
      rows.
- [ ] **Reviews due** is a **rolling** sixty days from whatever day you
      look at it, not "this quarter" or "next month". CAML has no
      calendar-period predicate, so a period-boundary reading has to come
      from your own reporting; the two differ at every boundary and anyone
      reconciling a committee pack will notice.
- [ ] List Settings → Indexed columns shows `ComplianceStatus`,
      `SourceType`, `ReviewDate` and `Owner`. The build manifest lists the
      same four under **indexed columns**.
- [ ] The New form shows **The duty**, **Assessment and evidence**,
      **Gaps and remediation** and **Ownership and cycle**, each holding
      the fields named in
      `20-configure/formatting/obligation-form-body.json`. There is no
      System section: nothing on this list is auto-stamped.
- [ ] The form reacts as you fill it in. On a New form, **Last assessed
      date** is absent while the status is *Not assessed*; choose any other
      status and it appears. Change back and it hides again, keeping
      whatever was typed — SharePoint has no mechanism to clear a hidden
      field's value.
- [ ] The list carries **two** chained save rules sharing one message,
      because SharePoint gives a list a single validation formula. Try
      each: set a status other than *Not assessed* with **Last assessed
      date** empty; set *Compliant*, *Partially compliant* or
      *Non-compliant* with **Evidence notes** empty. Both are refused, both
      show the same message naming both checks — that is the platform
      limit, not a defect, and it is why the future-date rule below lives
      on its column instead.
- [ ] **Last assessed date** refuses a future date with its own message,
      because it is a rule about one column and so keeps a message of its
      own.
- [ ] `ReviewDate` escalates to the severe treatment once it is past, on
      **every** row including *Not applicable* ones — this register has no
      terminal status and 50-govern reviews applicability like anything
      else, so the escalation is deliberately unguarded.
- [ ] As an ordinary Member: read-only.
- [ ] **Load the obligations** — start with ONE source (your accreditation
      standard, or one act) end-to-end rather than a thin layer of
      everything; a complete slice proves the method and becomes the
      pattern for the rest.
- [ ] Populate **CO Compliance Coordinators**; delete any test rows.
- [ ] Even as an owner: changing a deployed column's type, choices or
      settings is refused (sealed) and List settings offers no "Delete
      this list"; a display-name rename is still possible — it is
      drift, reverted and reported at the next re-paste.

## What is not enforced at save

The remediation pointer that 50-govern requires on every *Non-compliant*
and *Partially compliant* row is **not** a save rule. It lives in `Notes`,
which is rich text, and a SharePoint validation formula cannot reference a
multi-line column at all. It stays a governance check, and *The gap list*
view — which shows `Notes` beside the status — is where its absence is
visible.

## Redeploying

Bump `schema_version`, rebuild, re-paste. Existing rows are untouched;
drifted settings are reconciled, and declared views are reconciled to the
declaration — a view retitled by hand comes back under its declared title.
