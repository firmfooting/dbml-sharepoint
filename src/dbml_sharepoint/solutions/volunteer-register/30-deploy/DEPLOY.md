# Deploying the volunteer register (administrator)

Shared procedure: [`templates/README.md`](../../README.md) with
`<name> = volunteer-register`. Run order: **assess** the target site (paste
`build/assess.js`, read-only) → **review** `build/deploy-manifest.md` (must
show 0 validation errors) → **paste** `build/deploy.js` from a Site Owner's
console → **verify** against the checklist below. Template-specific notes
follow.

## Before you build

- [ ] `VL_` prefix free on the target site.
- [ ] **Privacy check**: site membership = volunteer coordinators + owners
      only (ordinary members get no grant by design; the site audience
      should match).
- [ ] Check names match your jurisdiction. Two ways to do it, and they are
      not equivalent:
      - **Re-label only** — edit `display_names.overrides.Volunteer` in
        `20-configure/mapping.yaml`. "WWCC Expiry" becomes "Blue Card
        Expiry" on every form and view, and nothing else moves.
      - **Rename the column** — edit `10-design/schema.dbml`. This moves
        the internal name, which the indexes, the five declared views and
        the reporting bundle all bind to, so every one of them has to be
        updated with it.
      Prefer the first unless you have a reason not to, and do either
      **before first deploy**.
- [ ] The role-requirements matrix in `50-govern/GOVERNANCE.md` is agreed.
      The register enforces what a formula can hold; the matrix holds the
      rest. See "What is enforced at save" there.
- [ ] The header shows `Volunteer: <name>` on a saved row and `New
      volunteer` before the name is typed, updating live.

## Optional: the seeded demonstration build

The expiry colours, the sweep views and the missing-checks surface are all
invisible on an empty list. To see them working, rebuild with `--seed`:

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

That bundle contains an extra file, `demo-data.js`. Paste `deploy.js`
first, then `demo-data.js`, from the same bundle. It creates six
volunteers — three active (one fully checked, one inside the 90-day expiry
window, one with a police check that was never recorded), an applicant in
the pipeline, one on extended leave and one exited and trimmed — so every
declared view has content on the day you demonstrate it.

The demo rows describe a **role**, not a person: this register holds
personal data, and seeding it with invented names would teach the wrong
reflex on the first screen anyone sees.

**Delete the demo rows before active use.** Every demo Title begins with
`[DEMO] `, they are matched by Title on re-paste (running it twice never
duplicates), and `rollback.js` treats a list whose rows are *all*
demo-marked as demo-only content. Do not seed a site that already holds
real volunteers.

## After the paste — verification checklist

- [ ] `VL_Volunteer` exists; `VolunteerRole` and `Coordinator` required.
- [ ] All five declared views appear: **Active by team** (the default),
      **Checks expiring 90 days**, **Missing checks**, **Pipeline**,
      **Inactive and exited**. If you seeded, none of them is empty. The
      generated **All Items** recovery view is hidden from the modern view
      bar because this template has an authored default.
- [ ] **Active by team** groups by Team. Grouping, not filtering: a
      volunteer with no Team lands in an unnamed group rather than
      disappearing.
- [ ] List Settings → Indexed columns shows `Status`, `Team`,
      `PoliceCheckExpiry` and `WWCCExpiry`. Those last two are what make
      the sweep views cheap.
- [ ] The New form shows four sections in this order: **Who they are**,
      **Checks and clearances**, **In the programme**, **Coordination**.
      Every column is in one of them.
- [ ] **Start Date** is absent on the New form (Status defaults to
      Applying) and appears the moment you move Status off **Applying**.
      Move it back and the field hides again, **keeping whatever was
      typed** — SharePoint has no mechanism to clear it, which is why the
      save rule below reads the value rather than the field.
- [ ] An expiry date in the past renders with the severe treatment and a
      warning icon; the same date on an **Exited** volunteer renders plain.
      The guard names Exited only — an Inactive volunteer's checks are
      still swept, because they intend to come back.
- [ ] Save rules, both of them:
      - Set **Induction Date** to tomorrow. Refused, with its own message
        about a future induction.
      - Set Status to **Active** with either Induction Date or Start Date
        empty. Refused, with the list's message.
- [ ] As an ordinary Member: **cannot see the list**.
- [ ] As a Coordinator: full create/edit.
- [ ] **Load current volunteers** — including the drawer of paper: every
      active volunteer with their real check expiry dates (this load is
      where most programmes discover their first expired check — that's
      the register working on day one).
- [ ] Populate **VL Volunteer Coordinators**; delete any test rows.
- [ ] Even as an owner: changing a deployed column's type, choices or
      settings is refused (sealed) and List settings offers no "Delete
      this list"; a display-name rename is still possible — it is
      drift, reverted and reported at the next re-paste.

### What "Missing checks" does and does not know

The view this template used to *recommend* was "Status = Active and a
required check column blank (per the role matrix)". The parenthesis is the
part a static view cannot do — SharePoint has no way to read a table in a
Markdown file, so no filter can know that an op-shop volunteer needs a WWCC
only if children are involved.

What ships is deliberately **wider than the matrix**: every active
volunteer missing *any* of police check, WWCC or induction. The coordinator
applies the matrix to the result. Over-reporting is the safe direction — a
row that turns out not to need a WWCC costs ten seconds of reading; a row
the view never showed costs a reportable failure.

## Redeploying

Bump `schema_version`, rebuild, re-paste. Rows untouched; views, forms,
formatting and save rules reconciled to the declaration.
