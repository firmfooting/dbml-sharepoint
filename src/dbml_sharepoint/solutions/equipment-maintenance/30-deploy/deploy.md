# Deploying equipment maintenance (administrator)

Shared procedure: [`templates/README.md`](../../README.md) with
`<name> = equipment-maintenance`. Run order: **assess** the target site
(paste `build/assess.js.txt`, read-only; the verdict must be COMPATIBLE or an
accepted DEGRADED) → **review** `build/deploy-manifest.md` (must show 0
validation errors) → **paste** `build/deploy.js.txt` from a Site Owner's
console → **verify** against the checklist below. Template-specific notes
follow.

## Before you build

- [ ] `EM_` prefix free on the target site.
- [ ] `EquipmentType` enum covers your maintained classes; frequency
      defaults per class agreed in `50-govern/governance.md`.
- [ ] **`Status` and `Result` members are named in deployed view filters,
      formatter maps and the save rule.** *Overdue* filters `Status = In
      service`; *Out of service* filters the full string `Out of service -
      awaiting maintenance`; *Failures* and *Actions arising* filter
      `Result`. Renaming one changes behaviour, not just wording. Decide
      **before first deploy**.
- [ ] If you also run the **asset-register** template: decide the boundary
      now — asset-register owns *what/where/whose*; this owns *is it in
      test*. Same physical tag string in both keeps them joinable by eye.
- [ ] The Equipment header shows `Item: <title>` on a saved row and `New
      maintained item` before the title is typed, updating live.

## Optional: the seeded demonstration build

**Read this one before you seed.** The *Overdue* view's target state on a
live register is **empty** — that is the whole point of the register, and
governance treats anything appearing there as work to be done or explained
within five business days.

The seeded build deliberately breaks that goal, and it should. A view that
demonstrates empty teaches the adopter it does not work; the first time
anyone should see *Overdue* populate must not be the first time a real
infusion pump is out of test. So the demo data ships **one genuinely
overdue item** — a pump eighteen days past its annual service and still in
service — which is simultaneously the clinical exposure this register is
bought for and the only way to see the view, the red date and the severity
colour render together.

Delete the demo rows before active use and the goal is restored.

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
first, then `demo-data.js.txt`, from the same bundle. It creates five
maintained items — one overdue and in service, one falling due inside
sixty days, one comfortably ahead, one failed and withdrawn, one retired —
and five service records covering every result.

The demo events carry **no evidence link**. A SharePoint URL column takes
a compound value and the demo writer emits plain literals, so a demo row
with a bare string in `Evidence URL` would fail at the paste rather than
in the build. Add one by hand on a test event to see the column render.

**Delete the demo rows before active use.** Every demo Title begins with
`[DEMO] `, so they are obvious in every view, they are matched by Title on
re-paste (running it twice never duplicates), and `rollback.js.txt` treats a
list whose rows are *all* demo-marked as demo-only content. Do not seed a
site that already holds a real schedule.

## After the paste — verification checklist

- [ ] `EM_Equipment` and `EM_MaintenanceEvent` exist (Equipment first).
- [ ] `EM_Equipment` has **The schedule** (the default), **Overdue**,
      **Due 60 days** and **Out of service**. `EM_MaintenanceEvent` has
      **Service history** (the default), **Failures** and **Actions
      arising**. If you seeded, none is empty — including *Overdue*, on
      purpose; see above. The generated **All Items** recovery view is
      hidden from the modern view bar on both lists.
- [ ] **What replaced "Per item".** The old recommended-views table asked
      for the service history of one item, and named accreditors and
      insurers as its readers. A static view cannot filter to one parent —
      building it meant hard-coding an item into a filter that rots, or
      one view per item. It ships as **Service history**: one view grouped
      on the Equipment lookup, collapsed. It is also the **default** on
      that list, because the audience governance names should not have to
      find a view picker first. An auditor expands the item they want and
      reads the same history, in date order, newest first.
- [ ] **Overdue filters `Status = In service`, not "not Retired".** That
      is deliberate and worth understanding before you rely on it: the
      view means *still in use and out of test*, which is the clinical and
      legal exposure. An item already withdrawn is overdue too, and it is
      in **Out of service**, where somebody is already looking.
- [ ] Create a test item (unique `EquipmentTag` enforced — try a
      duplicate); record an event against it (Equipment lookup offers it;
      PerformedBy and Result required).
- [ ] Set a test item's `Next Due Date` in the past while it is **In
      service**: the date turns red with a warning icon and the row appears
      in *Overdue*. Set `Status` to **Retired** and the red goes away — the
      guard names Retired only, so an item **Out of service** with a passed
      due date keeps shouting. That is intended: it is arguably the most
      urgent row in the register.
- [ ] Save rules, each with its own message: a `Frequency Months` below 1
      is refused (an interval of zero is a schedule that never advances),
      and an event dated in the future is refused. The MaintenanceEvent
      list refuses a **Passed with actions** or **Failed** event with no
      **Notes** — the actions and the reason have to land somewhere.
- [ ] Two things this register wants that are **not** enforced at save,
      and `50-govern/governance.md` explains both:
      - **Evidence on every event.** A URL column is a compound value and
        SharePoint validation formulas cannot read one.
      - **"An in-service item has a future-or-today Next Due Date"** —
        governance's own data-quality rule 1. As a save rule it would
        refuse to *store* an overdue item, which is the exact state the
        Overdue view exists to surface and the one a real register must be
        able to hold. A rule that makes a problem unrecordable does not
        fix it.
- [ ] The Equipment New form shows **The item**, **The schedule** and **In
      service**; the event form shows **The work**, **Outcome** and
      **Evidence**. Neither form has conditional fields, by design — every
      column on either list is true of the row from the moment it is
      created.
- [ ] As an ordinary Member: read-only.
- [ ] **Load the schedule** — every maintained item with its real
      Next Due Date (from the current binder/contractor list). An item not
      in the register is an item not in the schedule.
- [ ] Populate **EM Maintenance Team**; delete the test rows.
- [ ] Even as an owner: changing a deployed column's type, choices or
      settings is refused (sealed) and List settings offers no "Delete
      this list"; a display-name rename is still possible — it is
      drift, reverted and reported at the next re-paste.

## Redeploying

Bump `schema_version`, rebuild, re-paste.

## Enterprise reporting access

The deploy creates an empty `"EM Enterprise Readers"` site group holding `Read` on
every list in this family. It stays empty unless the build was run with
`--enterprise-reader <account>`, which enrols exactly that one account
and nothing else. `rollback.js.txt` does not remove it: rollback deletes
lists, not site groups or role assignments, so the group and any account
enrolled in it survive a rollback.
