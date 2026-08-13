# Deploying incident management (administrator)

Shared procedure: [`templates/README.md`](../../README.md) with
`<name> = incident-management`. Run order: **assess** the target site
(paste `build/assess.js.txt`, read-only; the verdict must be COMPATIBLE or an
accepted DEGRADED) → **review** `build/deploy-manifest.md` (must show 0
validation errors) → **paste** `build/deploy.js.txt` from a Site Owner's
console → **verify** against the checklist below. Template-specific notes
follow.

## Before you build

- [ ] `IN_` prefix free on the target site.
- [ ] `Severity` and `Category` enums match your incident taxonomy — the
      governance doc's severity definitions must agree with the choices.
      **`Critical` is named in a view formatter** (it drives the row wash
      on the default view) and every `Status` member is named in a view
      filter, a form rule or the save rule. Renaming one changes behaviour,
      not just wording. Decide **before first deploy**.
- [ ] You know who forms **IN Incident Handlers**.
- [ ] The Incident header shows `Incident: <title>` on a saved row and
      `New incident` before the title is typed, updating live.

## Optional: the seeded demonstration build

The severity ladder, the Critical row wash, the overdue action colouring
and six of the seven views are invisible on two empty lists. To see them
working, rebuild with `--seed`:

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
first, then `demo-data.js.txt`, from the same bundle. It creates six incidents
— one per status and one per severity band — and five corrective actions,
one per status. The pairing to look at is the open **Critical** incident
with an **overdue** action hanging off it: the pink row and the red date,
one click apart, are the whole argument for linking the two lists.

Nothing in the demo data is clinical, deliberately. This register is for
corporate and non-clinical incidents and the healthcare note in
`50-govern/governance.md` is emphatic about it.

**Delete the demo rows before active use.** Every demo Title begins with
`[DEMO] `, so they are obvious in every view, they are matched by Title on
re-paste (running it twice never duplicates), and `rollback.js.txt` treats a
list whose rows are *all* demo-marked as demo-only content. Do not seed a
site that already holds real incidents.

## After the paste — verification checklist

- [ ] `IN_Incident` and `IN_CorrectiveAction` exist; the custom permission
      level **IN Report Only** exists (Site settings → Site permissions →
      Permission levels).
- [ ] `IN_Incident` has **Open by severity** (the default), **Triage
      queue** and **Resolved last 90 days**. `IN_CorrectiveAction` has
      **Open actions** (the default), **Overdue**, **By owner** and **By
      incident**. If you seeded, none is empty. The generated **All Items**
      recovery view is hidden from the modern view bar on both lists.
- [ ] **What was added beyond the old recommended-views table**, which had
      only three rows:
      - **By incident** — corrective actions grouped under their incident,
        collapsed. Governance says an incident closes only when every
        linked action is Done or Cancelled, and nothing showed you that.
        It is also the quarterly sample's view: "check corrective actions
        were real, not paperwork" needs one incident's actions in one
        place.
      - **By owner** — governance chases overdue actions *by name*, and
        that was a sort-and-squint.
      - **Resolved last 90 days** — the monthly trend review's raw
        material. Two limits, stated because a board figure should not be
        built on a misunderstanding: it is a **rolling** ninety days,
        not a calendar quarter, because CAML has no calendar predicate.
        The mean IS there — `DaysToResolve` is averaged under each
        category and across the window — so only a quarter-aligned figure
        needs an export.
- [ ] An open **Critical** incident washes the whole row dusty rose in
      **Open by severity**. That is the one row-level signal this list
      declares, and the reason it reads is that nothing competes with it.
- [ ] Set ReportedDate `2026-07-01`, ResolvedDate `2026-07-08` →
      **Days To Resolve = 7**, drawn as a bar against a 30-day scale and
      coloured from that incident's **Severity**, not from its own value.
- [ ] A corrective action past its **Due Date** shows red with a warning
      icon, and stops once its Status is **Done** or **Cancelled**.
- [ ] The Incident New form shows five sections — **What happened**,
      **Triage**, **Resolution**, **Ownership**, **System**. **Handler**
      and **Resolved Date** are absent from it: a reporter is not asked who
      will run their incident or when it ended. On an existing incident,
      set Status to **Resolved** and **Resolved Date** appears. **System**
      holds only the calculated day-count, so on the New form it renders as
      a bare heading — cosmetic and expected.
- [ ] The action form shows **The action**, **Progress**, **Ownership**.
      **Done Date** is off the New form and appears once Status is
      **Done**.
- [ ] Save rules, each with its own message: no incident date may be in
      the future, and no action Done Date may be either. The Incident list
      refuses **Resolved** or **Closed** with no **Resolved Date**; the
      action list refuses **Done** with no **Done Date**.
- [ ] Three rules governance states that **cannot** be enforced at save,
      and `50-govern/governance.md` says why:
      - *Every incident past Reported has a Handler* — SharePoint
        validation formulas cannot reference person columns at all.
      - *Closed requires all linked actions terminal* — the actions are on
        another list, and a save rule reaches only its own. **By incident**
        is the reconciliation.
      - *A cancelled action says why in Notes* — Notes is rich text, which
        validation formulas cannot reference either.
- [ ] As an ordinary Member: you can **New** an incident but the saved row
      shows no Edit for you — and you cannot edit anyone else's.
- [ ] As a Handler: you can edit the test incident, set `Handler`, and add
      a linked corrective action (the Incident lookup offers the test row).
- [ ] Populate **IN Incident Handlers**; delete the test rows (as Handler).
- [ ] Even as an owner: changing a deployed column's type, choices or
      settings is refused (sealed) and List settings offers no "Delete
      this list"; a display-name rename is still possible — it is
      drift, reverted and reported at the next re-paste.

## Redeploying

Bump `schema_version`, rebuild, re-paste. The report-only level's
permissions are reconciled on every run — drift is corrected, not accepted.

## Enterprise reporting access

The deploy declares the `dbml Enterprise Readers` site group — shared with every
other family deployed to the site — and grants it `Read` on every list in this
family. The group starts empty only if no family has deployed to the site yet;
it gains a member when any family's build is run with `--enterprise-reader
<account>`, which enrols exactly that one account and nothing else.
`rollback.js.txt` does not remove it: rollback deletes lists, not site groups
or role assignments, so the group and any account enrolled in it survive a
rollback.

A later build that omits the flag does not put the group back to empty:
enrolment only runs when `--enterprise-reader` is given, so an account enrolled
by an earlier build — of this family or any other sharing the site — keeps its
membership and its `Read` grant on every list it was declared against. Removing
it is manual — clear it in Site permissions > Groups.

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
