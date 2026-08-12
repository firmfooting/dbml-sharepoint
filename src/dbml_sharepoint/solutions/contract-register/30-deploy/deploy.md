# Deploying the contract register (administrator)

Shared procedure: [`templates/README.md`](../../README.md) with
`<name> = contract-register`. Run order: **assess** the target site (paste
`build/assess.js.txt`, read-only; the verdict must be COMPATIBLE or an accepted
DEGRADED) → **review** `build/deploy-manifest.md` (must show 0 validation
errors) → **paste** `build/deploy.js.txt` from a Site Owner's console → **verify**
against the checklist below. Template-specific notes follow.

## Before you build

- [ ] `CT_` prefix free on the target site? (Site contents — no `CT_*` lists.)
- [ ] `ContractType` / `Status` / `RenewalType` choices match your
      vocabulary (`10-design/schema.dbml`) — renaming choices after data
      exists strands old rows, and `Status` and `RenewalType` are both
      colour-mapped in `mapping.yaml`, so a renamed member also silently
      loses its colour.
- [ ] **Decide your expiry horizon before first deploy.** The
      *Expiring 90 days* view filters `EndDate ≤ today+90`. If your renewal
      governance runs on a different cadence, change the `today+90` in
      `mapping.yaml` now — a view title and a filter that disagree is worse
      than either.
- [ ] You know who goes in **CT Contract Managers** (the deploy creates it
      empty; you populate it after).
- [ ] The header shows `Contract: <title>` on a saved row and
      `New contract` before the title is filled in, updating live as it is
      typed. If you add another `[$FieldName]` reference, note that a
      **calculated** column always resolves empty in a form header —
      `TermMonths` will show nothing there, with no error. Its value reaches
      the form through its own `column_formatting`, in the **System**
      section.

**Expected manifest finding**: one warning — `Contract.ContractRef: unique
without not_null` — is intentional: the reference is optional, and
uniqueness is enforced on the rows that have one.

## Optional: the seeded demonstration build

The expiry colours, the term bar and every declared view are invisible on
an empty list. To see them working, rebuild with `--seed`:

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
then `demo-data.js.txt`, from the same bundle. It creates five rows — one per
`Status` member, including a licence that auto-renews and is *already*
inside its own ninety-day notice window — enough that every declared view
and every colour band has content.

**Delete the demo rows before active use.** Every demo Title begins with
`[DEMO] `, so they are obvious in every view, they are matched by Title on
re-paste (running it twice never duplicates), and `rollback.js.txt` treats a
list whose rows are *all* demo-marked as demo-only content. Do not seed a
site that already holds real contracts.

## After the paste — verification checklist

- [ ] `CT_Contract` exists and all five declared views appear:
      **Live contracts** (the default), **Expiring 90 days**,
      **Auto-renewals**, **By counterparty**, **Exited**. If you seeded,
      none of them is empty. The generated **All Items** recovery view is
      hidden from the modern view bar because this template has an authored
      default.
- [ ] **By counterparty** is grouped and collapsed on `Counterparty`. The
      old *Recommended views* table asked for exactly this and left you to
      build it; it now deploys.
- [ ] **Expiring 90 days** is a **rolling** ninety days from whatever day
      you look at it, not "this quarter". CAML has no calendar-period
      predicate, so a quarter-boundary reading has to come from your own
      reporting; the two differ on the first day of a quarter and anyone
      reconciling a procurement pack will notice.
- [ ] List Settings → Indexed columns shows `Status`, `EndDate` and
      `ContractType`. The build manifest lists the same three under
      **indexed columns**.
- [ ] Create a test row with StartDate `2026-01-01`, EndDate `2027-06-30` →
      **Term (months) shows 17** automatically, as a data bar against a
      five-year scale.
- [ ] `ContractRef` rejects a duplicate value (unique constraint).
- [ ] The New form shows **The contract**, **Term and value** and
      **Ownership**, each holding the fields named in
      `20-configure/formatting/contract-form-body.json`. **System** is last
      and holds `TermMonths` only — it is calculated, so on the New form
      that section is a bare heading with nothing under it. That is
      cosmetic and expected; on the Edit and Display forms the calculated
      value appears there, read-only.
- [ ] The form reacts as you fill it in. On a New form, set
      **Renewal type** to *Fixed term — no renewal* and **Notice period
      days** disappears; set it back to *Auto-renews* or *Manual renewal*
      and the field returns, keeping whatever was typed. SharePoint has no
      mechanism to clear a hidden field's value, so a stale notice period
      can survive a switch to a fixed term — harmless here, because nothing
      reads it in that state.
- [ ] The list carries **one** save rule: set **Renewal type** to
      *Auto-renews* with **Notice period days** empty and the save is
      refused, naming the notice period. Note the field is on screen when
      the refusal fires — a rejection naming a field the author cannot see
      is what the visibility rule above exists to prevent.
- [ ] Two per-column save rules, each with its own message: a negative
      **Notice period days** and a negative **Annual value** are both
      refused, and each says why. These live on their columns rather than
      on the list because a column rule keeps its own message; the list has
      only one to share.
- [ ] `EndDate` renders plain while the date is ahead and escalates to the
      severe treatment once it is past — except on an **Exited** row, where
      the escalation is suppressed. Set a test row to Exited and confirm
      the colour drops.
- [ ] As an ordinary site Member: the list is **read-only**.
- [ ] Site permissions → Groups: `CT Contract Managers` (empty — now add
      your contract managers) and `CT List Administrators` (empty — leave
      it empty; the deploy script self-enrols per run).
- [ ] Delete the test row (as a Contract Manager).
- [ ] Even as an owner: changing a deployed column's type, choices or
      settings is refused (sealed) and List settings offers no "Delete
      this list"; a display-name rename is still possible — it is
      drift, reverted and reported at the next re-paste.

## What is not enforced at save

`EndDate` after `StartDate` is **not** a save rule. The condition grammar
compares a column to a literal, never to another column, so the rule has no
spelling — it stays a governance check (`50-govern/governance.md`). The
*Live contracts* view sorted by `EndDate` is where a reversed pair shows
up: it sorts to the top, years in the past.

## Redeploying after a schema change

Edit the DBML/mapping, bump `schema_version` in `release.yaml`, rebuild,
re-paste. Existing rows are untouched; drifted settings are reconciled, and
declared views are reconciled to the declaration — a view retitled by hand
comes back under its declared title.

## Enterprise reporting access

The deploy creates an empty `"CT Enterprise Readers"` site group holding `Read` on
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
