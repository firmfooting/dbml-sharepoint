# Deploying the delegations register (administrator)

Shared procedure: [`templates/README.md`](../../README.md) with
`<name> = delegations-register`. Run order: **assess** the target site
(paste `build/assess.js.txt`, read-only; the verdict must be COMPATIBLE or an
accepted DEGRADED) → **review** `build/deploy-manifest.md` (must show 0
validation errors) → **paste** `build/deploy.js.txt` from a Site Owner's
console → **verify** against the checklist below. Template-specific notes
follow.

## Before you build

- [ ] **Replace the instrument link in the form header.** This is the only
      template in the governance theme whose header carries an external
      link, and it ships as a placeholder:
      `https://REPLACE-WITH-INSTRUMENT-OF-DELEGATION-URL` in
      `20-configure/formatting/delegation-form-header.json`. Point it at
      your approved instrument of delegation before you build, or delete
      the `elmType: "a"` element. **A form deployed with the placeholder
      hands a dead link to every person who opens a delegation** — and this
      register's whole doctrine is that when the register and the
      instrument disagree, the instrument wins, so that link is the one
      thing on the form that has to work.
      Use an **absolute `https://` address**. SharePoint's formatter emits
      only `http`, `https`, `mailto` and `tel` links, so a site-relative
      path such as `/sites/governance/...` is not a valid substitution.
- [ ] `DG_` prefix free on the target site.
- [ ] The current instrument of delegation is at hand — the register is
      loaded FROM it, clause by clause; it never invents an authority.
- [ ] `DelegationArea` matches your instrument's own structure
      (`10-design/schema.dbml`). It is the grouping level of the default
      view, so its members become that view's headings.
- [ ] **Decide your review horizon before first deploy.** The *Reviews
      due* view filters `ReviewDate ≤ today+90`. Change the `today+90` in
      `mapping.yaml` now if your governance calendar differs.
- [ ] You know who forms **DG Governance Coordinators**.
- [ ] The header shows `Delegation: <title>` on a saved row and
      `New delegation` before the title is filled in, updating live as it
      is typed.

## Optional: the seeded demonstration build

The status colours, the overdue review dates and both grouped views are
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

That bundle contains an extra file, `demo-data.js.txt`. Paste `deploy.js.txt`
first, then `demo-data.js.txt`, from the same bundle. It creates five rows —
four current authorities across four areas and four roles, so both grouped
views have more than one group, two of them inside the ninety-day review
window, and one superseded row carrying its supersession trail.

**Delete the demo rows before loading from your instrument.** Every demo
Title begins with `[DEMO] `, so they are obvious in every view, they are
matched by Title on re-paste (running it twice never duplicates), and
`rollback.js.txt` treats a list whose rows are *all* demo-marked as demo-only
content. A demo delegation left in a live register is an authority nobody
approved.

## After the paste — verification checklist

- [ ] `DG_Delegation` exists; `RoleHolder`, `SourceInstrument` and
      `ReviewDate` required.
- [ ] All four declared views appear: **By area** (the default),
      **By role**, **Reviews due**, **History**. If you seeded, none of
      them is empty. The generated **All Items** recovery view is hidden
      from the modern view bar because this template has an authored
      default.
- [ ] **By area** and **By role** are grouped and collapsed, and both
      filter to `Status = Current`. That filter is deliberate: a register
      answering "what may I approve" with superseded authority mixed in is
      worse than not answering.
- [ ] **Reviews due** filters on `Status = Current` **as well as** the
      date. The old *Recommended views* table specified the date alone; a
      superseded row's review date is a fact about a delegation that no
      longer exists, and leaving those in the queue asks the quarterly
      spot-check to re-review authority nobody holds. It is also a
      **rolling** ninety days, not "this quarter" — CAML has no
      calendar-period predicate, and the two differ at every boundary.
- [ ] **History** sorts on `ApprovedDate` descending and shows `Notes`,
      which is where the supersession trail lives.
- [ ] The instrument link in the form header opens **your** instrument,
      not a placeholder. Check this on the deployed form, not in the JSON.
- [ ] List Settings → Indexed columns shows `DelegationArea`, `Status` and
      `RoleHolder`. The build manifest lists the same three under
      **indexed columns**.
- [ ] The New form shows **The authority**, **Limit and conditions** and
      **Source and review**, each holding the fields named in
      `20-configure/formatting/delegation-form-body.json`. There is no
      System section, and nothing on this form is conditional — every
      column applies to every row, including a superseded one, whose limit
      and conditions are exactly what an auditor is reading.
- [ ] The list carries **one** save rule: set `Status` to **Superseded**
      with `Notes` empty and the save is refused, naming what the note has
      to say.
- [ ] `ApprovedDate` refuses a future date with its own message. That rule
      lives on its column rather than on the list because a column rule
      keeps a message of its own; the list has only one to share.
- [ ] `ReviewDate` escalates to the severe treatment once it is past, and
      the escalation is suppressed on a **Superseded** row. Set a test row
      to Superseded and confirm the colour drops.
- [ ] As an ordinary Member: read-only.
- [ ] **Load from the instrument** — one row per delegable authority,
      role-not-person, limits and conditions in the instrument's own
      wording. Where the transcription feels ambiguous, that's a finding
      about the instrument: note it for the next instrument review rather
      than smoothing it over.
- [ ] Populate **DG Governance Coordinators**; delete any test rows.
- [ ] Even as an owner: changing a deployed column's type, choices or
      settings is refused (sealed) and List settings offers no "Delete
      this list"; a display-name rename is still possible — it is
      drift, reverted and reported at the next re-paste.

## What is not enforced at save

- **`RoleHolder` naming a role rather than a person.** This is the
  register's most important editorial rule and it is a free-text column;
  no formula can tell "Director of Nursing" from "Jane Chen". The
  quarterly verbatim spot-check in `50-govern/governance.md` is the
  control.
- **Limits and conditions being verbatim.** Same reason. A save rule can
  prove text exists; it cannot prove the text matches the instrument.
- **A `SourceInstrument` clause that actually exists.** The register cannot
  read the instrument, which is exactly why the header links to it.

## Redeploying

Bump `schema_version`, rebuild, re-paste. Existing rows are untouched;
drifted settings are reconciled, and declared views are reconciled to the
declaration — a view retitled by hand comes back under its declared title.
**Re-check the header link after any redeploy**: the header JSON is
reconciled from the file, so a URL edited in the SharePoint UI is reverted
to whatever the file says.

## Enterprise reporting access

The deploy creates an empty `"DG Enterprise Readers"` site group holding `Read` on
every list in this family. It stays empty unless the build was run with
`--enterprise-reader <account>`, which enrols exactly that one account
and nothing else. `rollback.js.txt` does not remove it: rollback deletes
lists, not site groups or role assignments, so the group and any account
enrolled in it survive a rollback.

A later build that omits the flag does not put the group back to empty:
enrolment only runs when `--enterprise-reader` is given, so an account
enrolled by an earlier build keeps its membership and its `Read` grant on
every list. Removing it is manual — clear it in Site permissions > Groups.

If the group already holds anyone other than that account, the deploy
**aborts before enrolling** and removes nobody — clear it in Site
permissions > Groups and paste again, or rebuild without the flag.

On one Microsoft 365 group-connected Team Site (measured 2026-08-11) the
enrolled account ends up with the built-in `Read` on each list and
`Use Remote Interfaces` intact at web scope. Publishing sites — where
lockdown mode is on by default — and the reporting client's own list
enumeration are still unverified, so the end-to-end path (Power BI or any
other API client) is not yet proven. See the danger block in the mapping
reference's Security section.
