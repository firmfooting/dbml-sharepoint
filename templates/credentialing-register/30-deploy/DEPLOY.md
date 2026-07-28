# Deploying the credentialing register (administrator)

Shared procedure: [`templates/README.md`](../../README.md) with
`<name> = credentialing-register`. Run order: **assess** the target site
(paste `build/assess.js`, read-only) → **review**
`build/deploy-manifest.md` (must show 0 validation errors) → **paste**
`build/deploy.js` from a Site Owner's console → **verify** against the
checklist below. Template-specific notes follow.

## Before you build

- [ ] `CR_` prefix free on the target site.
- [ ] `Discipline`/`CredentialType` enums match your workforce.
- [ ] **Privacy check**: site membership reviewed — the register holds
      staff professional data and the visibility decision in
      `50-govern/GOVERNANCE.md` is made and recorded.
- [ ] You know who forms **CR Credentialing Coordinators**.
- [ ] **Decide which disciplines carry a registration number.** The
      template hides `RegistrationNumber` and `RegistrationExpiry` when
      `Discipline` is **Other credentialed role**, following the schema's
      own note that non-registered credentialed roles have none. Which
      disciplines are registered is jurisdictional; if yours differ, edit
      `form_visibility.Practitioner` in `20-configure/mapping.yaml`. Both
      fields are optional, so getting this wrong costs a hidden field
      rather than a failed save — but the fields are also *sealed* after
      deploy, so this cannot be corrected in the UI.
- [ ] Decide your two windows. Registrations sweep at **today+90** and
      scope reviews at **today+60**; both numbers live once each, in the
      views, and both view titles are deliberately silent about them so
      changing one does not leave a title lying.
- [ ] Each header shows `Practitioner: <name>` / `Credential: <title>` on
      a saved row and `New practitioner` / `New credential` before the
      title is typed, updating live.

**Expected manifest finding**: one warning — `Practitioner.RegistrationNumber:
unique without not_null` — is intentional: non-registered credentialed
roles have no registration number, and uniqueness is enforced on the rows
that do. It is the only warning; anything else is worth reading.

### On the guide link in the form header — there isn't one, deliberately

The family standard permits a themed link to an external document in a
form header, and named this register as one of four templates that might
genuinely earn one. It does not, and the reasoning is worth having where
someone will look for it before adding one.

The document this register defers to is *your* by-laws and *your*
credentialing committee's terms of reference — a class of document, not a
document the template can name. The only link shippable from here is a
`REPLACE-WITH-...` placeholder, and this form is exactly where that is
most dangerous: it is where a coordinator transcribes a committee
decision, and a dead link in its header implies the authority is one click
away when it is not.

**Adding a real one is two lines** in
`20-configure/formatting/practitioner-form-header.json`, beside the
strapline:

```json
{
  "elmType": "a",
  "attributes": {
    "href": "https://yourtenant.sharepoint.com/sites/governance/credentialing-by-laws.aspx",
    "target": "_blank",
    "class": "ms-fontColor-themePrimary ms-fontSize-12"
  },
  "txtContent": "Credentialing by-laws"
}
```

Use an **absolute `https://` address**. SharePoint's formatter emits only
`http`, `https`, `mailto` and `tel` links, so a site-relative path is not
a valid substitution — it renders as text that looks like a link and does
nothing.

## Optional: the seeded demonstration build

The expiry colours, the row wash on an expired credential and the two
grouped views are invisible on empty lists. To see them working, rebuild
with `--seed`:

```bash
dbml-sharepoint build \
  --schema templates/credentialing-register/10-design/schema.dbml \
  --mapping templates/credentialing-register/20-configure/mapping.yaml \
  --release templates/credentialing-register/20-configure/release.yaml \
  --site-url https://yourtenant.sharepoint.com/sites/your-site \
  --site-role default \
  --seed \
  --out ./build
```

That bundle contains an extra file, `demo-data.js`. Paste `deploy.js`
first, then `demo-data.js`, from the same bundle. It creates five
practitioners — one per status, including a non-registered credentialed
role that demonstrates the hidden registration pair — and six credentials
including two that have lapsed.

The practitioner titles describe a **role**, not a person: this register
holds staff professional data, and seeding it with invented names would
teach the wrong reflex on the first screen anyone sees.

**Every demo credential has a blank Evidence URL**, so on a seeded site
every Current credential appears in *Missing evidence*. That is the
mechanism rather than a defect — a SharePoint URL column takes a
structured value over REST rather than a bare string, and this repository
does not seed a write it has not read back from a live list. It also makes
the best available demonstration of that view: paste a URL onto one row by
hand and watch it leave.

**Delete the demo rows before active use.** Every demo Title begins with
`[DEMO] `, they are matched by Title on re-paste (running it twice never
duplicates), and `rollback.js` treats a list whose rows are *all*
demo-marked as demo-only content. Do not seed a site that already holds
real practitioners.

## After the paste — verification checklist

- [ ] `CR_Practitioner` and `CR_Credential` exist (Practitioner first).
- [ ] All five **Practitioner** views appear: **By discipline** (the
      default, grouped and collapsed), **Registrations expiring**, **Scope
      reviews due**, **Under review or lapsed**, **Ceased**.
- [ ] All four **Credential** views appear: **By practitioner** (the
      default, grouped by the Practitioner lookup and collapsed),
      **Expiring credentials**, **Missing evidence**, **Expired**. If you
      seeded, none of the nine is empty. The generated **All Items**
      recovery view is hidden from the modern view bar on both lists,
      because each has an authored default.
- [ ] In **By practitioner**, an Expired credential's whole row carries a
      dusty-rose wash. That is the one row-level signal on this register,
      reserved for the one state it exists to make impossible to miss.
      Nothing else competes with it.
- [ ] The Practitioner form shows **The practitioner**, **Registration**,
      **Scope of practice** and **Standing**. The Credential form shows
      **The credential**, **Issue and expiry**, **Evidence** and
      **Standing**. Every column sits in one of them.
- [ ] On a new practitioner, **Registration Number** and **Registration
      Expiry** are visible while Discipline is blank. Choose **Other
      credentialed role** and both disappear; choose anything else and
      they come back.
- [ ] A registration expiry or scope review date in the past renders with
      the severe treatment and a warning icon. Set that practitioner to
      **Ceased** and both go plain — at Ceased they are history rather
      than deadlines. **Lapsed** and **Under review** deliberately keep
      shouting: that is precisely when someone is deciding what the person
      may still do.
- [ ] Save rules, all four:
      - A **Scope Approved Date** in the future is refused.
      - A practitioner set to **Current** with no Scope Approved Date is
        refused, with the list's message.
      - An **Issued Date** in the future is refused.
      - A credential set to **Expired** with no Expiry Date is refused.
- [ ] Create a test practitioner; add a credential against them (the
      Practitioner lookup offers the row); `RegistrationNumber` rejects a
      duplicate.
- [ ] As an ordinary Member: read-only.
- [ ] **Load the workforce** — the register is only trustworthy complete:
      every credentialed practitioner, their current scope decision and
      review date, then their credentials with expiries. Budget real time
      for this; it is the project.
- [ ] Populate **CR Credentialing Coordinators**; delete the test rows.
- [ ] Even as an owner: changing a deployed column's type, choices or
      settings is refused (sealed) and List settings offers no "Delete
      this list"; a display-name rename is still possible — it is
      drift, reverted and reported at the next re-paste.

### "Per practitioner", and what ships instead

The old table specified a Credential view *filtered to one practitioner* —
the credentialing-file view. A static view cannot filter to one parent
record, so the choices were N views that rot as the workforce changes, or
one grouped view that does not.

What ships is **By practitioner**: grouped by the Practitioner lookup,
collapsed, and deliberately **unfiltered**. Opening a practitioner's group
*is* their credentialing file, and the expired and withdrawn rows belong
in it — a file that hid the lapses would be the opposite of the point.

## Redeploying

Bump `schema_version`, rebuild, re-paste. Rows untouched; views, forms,
formatting and save rules reconciled to the declaration.
