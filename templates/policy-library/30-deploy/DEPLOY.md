# Deploying the policy library (administrator)

Shared procedure: [`templates/README.md`](../../README.md) with
`<name> = policy-library`. Run order: **assess** the target site (paste
`build/assess.js`, read-only; the verdict must be COMPATIBLE or an accepted
DEGRADED) → **review** `build/deploy-manifest.md` (must show 0 validation
errors) → **paste** `build/deploy.js` from a Site Owner's console →
**verify** against the checklist below. Template-specific notes follow.

> **This template is uplifted on one side only.** `PL_PolicyRegister` gets
> declared views, a sectioned form, conditional fields, save rules and demo
> data like every other register in the library. `PL_PolicyDocuments` is a
> **document library**, and three parts of the fleet standard do not
> describe one — the reasons are set out under
> [The library half](#the-library-half-still-manual-and-why) below, and
> the one library view you were asked to build by hand is still yours to
> build.

## Before you build

- [ ] `PL_` prefix free on the target site.
- [ ] `PolicyArea` enum matches your policy framework's domains. It is the
      grouping level of the register's default view, so its members become
      that view's headings — and `Status` is colour-mapped in
      `mapping.yaml`, so a renamed member strands old rows *and* silently
      loses its colour.
- [ ] **Decide your review horizon before first deploy.** The *Review due*
      view filters `ReviewDate ≤ today+90`, matching the ninety-day window
      in `50-govern/GOVERNANCE.md`. Change both together if yours differs.
- [ ] **Check the `ReviewMonths` data bar against your own interval.** It
      scales to `max: 36`, the ceiling governance names for low-risk areas,
      so a policy on a longer cycle pins the bar full and reads as an
      outlier. If your standard interval is longer, move the `max`.
- [ ] You know who forms **PL Policy Authors**.
- [ ] The register header shows `Policy: <title>` on a saved row and
      `New policy` before the title is filled in, updating live as it is
      typed. If you add another `[$FieldName]` reference, note that a
      **calculated** column always resolves empty in a form header —
      `ReviewMonths` will show nothing there, with no error. Its value
      reaches the form through its own `column_formatting`, in the
      **System** section.

## Optional: the seeded demonstration build

The status colours, the review-interval bar and every declared register
view are invisible on an empty list. To see them working, rebuild with
`--seed`:

```bash
dbml-sharepoint build \
  --schema templates/policy-library/10-design/schema.dbml \
  --mapping templates/policy-library/20-configure/mapping.yaml \
  --release templates/policy-library/20-configure/release.yaml \
  --site-url https://yourtenant.sharepoint.com/sites/your-site \
  --site-role default \
  --seed \
  --out ./build
```

That bundle contains an extra file, `demo-data.js`. Paste `deploy.js`
first, then `demo-data.js`, from the same bundle. It creates six register
rows — one per `Status` member, each in a different policy area so every
group heading in the default view appears with content under it, and a
published policy whose review falls inside the ninety-day window.

**There are no demo documents**, and that is deliberate: an item created in
a document library through the list API is metadata with no file behind it.
Upload a test file yourself for the versioning checks below.

**Delete the demo rows before loading your real policies.** Every demo
Title begins with `[DEMO] `, so they are obvious in every view, they are
matched by Title on re-paste (running it twice never duplicates), and
`rollback.js` treats a list whose rows are *all* demo-marked as demo-only
content.

## After the paste — verification checklist

- [ ] `PL_PolicyDocuments` (document **library**) and `PL_PolicyRegister`
      (list) both exist.
- [ ] The register shows four declared views: **By area** (the default),
      **Review due**, **In development**, **Retired**. If you seeded, none
      of them is empty. The generated **All Items** recovery view is hidden
      from the modern view bar because the register has an authored
      default. The **library** has no declared views — see below.
- [ ] **By area** is grouped and collapsed on `PolicyArea` and filters out
      superseded and withdrawn policies. That filter is the point: a
      register that answers "what is our policy on X" with a superseded
      policy is worse than one that does not answer.
- [ ] **Review due** is a **rolling** ninety days from whatever day you
      look at it. CAML has no calendar-period predicate, so a
      month-boundary reading has to come from your own reporting.
- [ ] **In development** was not in the old *Recommended views* table and
      is the gap this register was worst at showing: a policy sitting at
      **Approved** is decided and unreadable — the document has not reached
      staff. Those rows render **amber**, not green, and this view is where
      they are meant to be cleared from.
- [ ] Library versioning: Library settings → Versioning shows **major AND
      minor** versions enabled. Upload a test file → it lands as **0.1**
      (a draft); Publish it (… → More → Publish) → **1.0**.
- [ ] Register: create a test policy with ApprovedDate `2026-07-01` and
      ReviewDate `2028-07-01` → **ReviewMonths = 24**, rendered as a bar
      two-thirds of the way to the thirty-six-month ceiling.
- [ ] The register's New form shows **The policy**, **The current version**
      and **Review and history**, each holding the fields named in
      `20-configure/formatting/policyregister-form-body.json`. **System**
      is last and holds `ReviewMonths` only — it is calculated, so on the
      New form that section is a bare heading with nothing under it. That
      is cosmetic and expected; on Edit and Display the value appears
      there, read-only.
- [ ] The register form reacts as you fill it in. On a new policy at
      **Draft**, **Approved date** and **Document URL** are both absent —
      a policy is registered before it is written, so there is nothing to
      approve or link yet. Move the status to *Approved* and the date
      appears; move it to *Published* and the link appears too. Moving back
      hides them again while keeping whatever was typed; SharePoint has no
      mechanism to clear a hidden field.
- [ ] The register carries **one** save rule: set **Status** to *Approved*
      or *Published* with **Approved date** empty and the save is refused.
      It is what the review interval is measured from, so without it
      `ReviewMonths` stays blank and the policy drops out of the outlier
      check governance relies on.
- [ ] One per-column save rule with its own message: a future **Approved
      date** is refused.
- [ ] `ReviewDate` escalates to the severe treatment once it is past, and
      the escalation is suppressed on **Superseded** and **Withdrawn**
      rows.
- [ ] **Set Draft Item Security — the deploy does not.** Library settings →
      Versioning settings → *Draft Item Security* → **"Only users who can
      edit"** → OK. SharePoint's default is "Any user who can read items",
      and nothing in `mapping.yaml` changes it: minor versioning and draft
      visibility are independent properties, and the deployer only writes
      the first. Skip this and every draft is readable by every staff
      member, which is the opposite of what this template is for.
- [ ] As an ordinary Member: both are read-only, and — **after** the step
      above — the library shows only the **published** (major) version of
      your test file, not the 0.1 draft. Check this as a Member, not as
      yourself; an author sees drafts either way.
- [ ] Populate **PL Policy Authors**; delete the test file and row.
- [ ] Even as an owner: changing a deployed column's type, choices or
      settings is refused (sealed) and List settings offers no "Delete
      this list"; a display-name rename is still possible — it is
      drift, reverted and reported at the next re-paste.

## The library half: still manual, and why

The register's two recommended views now deploy. The **library's** one does
not, and neither does a library form or library demo data. Each was tried
and each failed for a reason worth writing down rather than working around:

| What the standard asks for | What happens on a document library |
|---|---|
| A declared view with the file in it | `views[].fields` accepts DBML columns plus `ID`/`Created`/`Modified`/`Author`/`Editor`. `FileLeafRef` — the file name — is none of those, and naming it is a **build error**. A documents view with no file name is a view nobody can open a document from. |
| A sectioned form body | Same column, same refusal. A declared body would lay out the metadata and leave the document itself out of the layout. |
| A header with a live title line | The standard's line is `=if([$Title] == '', …)`. On a document library `Title` is a separate field that SharePoint does **not** populate from the file name, so the header would read *New document* on every saved document, forever. |
| Demo rows | These build cleanly, which is the dangerous part: they generate a POST that asks SharePoint to create a library item **with no file behind it**. Not shipped on an assumption. |

So build this one by hand, once, in the library's own view editor:

| Where | View | Filter |
|---|---|---|
| Library | Drafts in progress | `Document Status` = Draft or In review |

It is a per-site view like any other you create yourself, and the deployer
never touches it — undeclared views are not reconciled, so a redeploy will
not remove it.

## What is not enforced at save

- **The supersession trail** a retired policy must carry. It lives in
  `Notes`, which is rich text, and a SharePoint validation formula cannot
  reference a multi-line column at all. The *Retired* view shows `Notes`
  beside each row for exactly that reason.
- **A published policy having a `DocumentUrl`.** It is a hyperlink column,
  and **SharePoint will not accept a validation formula that references
  one** — it answers HTTP 500, *"One or more column references are not
  allowed, because the columns are defined as a data type that is not
  supported in formulas."* Established against a live tenant; the build
  refuses the operand, so a mapping that tries this fails to build rather
  than failing your paste. The *By area* and *Review due* views both show
  the column, so an empty one is visible in the monthly review.
- **Register ↔ library agreement.** `Status` on the row and `Document
  Status` on the file are on two different lists with no link between them;
  no formula spans that. The five-minute orphan check in
  `50-govern/GOVERNANCE.md` is the control, and it is the reason the
  library's own drafts view is still worth building.

## Redeploying

Bump `schema_version`, rebuild, re-paste. Files and rows are untouched;
declared settings (including the minor-versioning flag) are reconciled.
