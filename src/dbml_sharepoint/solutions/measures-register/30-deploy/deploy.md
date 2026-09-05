# Deploying the measures register (administrator)

Shared procedure: [`templates/README.md`](../../README.md) with
`<name> = measures-register`. Run order: **assess** the target site (paste
`build/assess.js.txt`, read-only; the verdict must be COMPATIBLE or an accepted
DEGRADED) -> **review** `build/deploy-manifest.md` (must show 0 validation
errors) -> **paste** `build/deploy.js.txt` from a Site Owner's console -> **verify**
against the checklist below. Template-specific notes follow.

## Before you build

- [ ] `MR_` prefix free on the target site.
- [ ] You know who forms **MR Measure Custodians** (small, definitions
      need guarding, not committees).
- [ ] `MeasureArea` is free text, not an enum. Agree the handful of area
      names **before** loading the catalogue: "The catalogue" groups on
      this column, and "Quality", "quality" and "Quality & Safety" group as
      three areas.
- [ ] Decide the review cadence you will actually run. The save rule ships
      at **twelve months**: a review date further out than that is
      refused, because a measure nobody re-tests within a year has quietly
      left the annual cull in `50-govern/governance.md`. Changing the
      cadence means changing `column_validation` in `mapping.yaml` before
      first deploy.
- [ ] The header shows `Measure: <title>` on a saved row and `New measure`
      before the title is typed, updating live. This list has no calculated
      columns, so the header trap that bites the rest of the theme (a
      calculated column always resolves empty in a form header, silently)
      does not arise here. It still applies if you add one.

## Optional: the seeded demonstration build

The five declared views, the status colours and the overdue review-date
escalation are all invisible on an empty list. To see them working, rebuild
with `--seed`:

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
then `demo-data.js.txt`, from the same bundle. It creates six rows (four Active
measures across four areas and four forums, one Under development with no
review date, and one Retired), enough that every declared view has content
and every status colour renders.

**Delete the demo rows before active use.** Every demo Title begins with
`[DEMO]`, so they are obvious in every view, they are matched by Title on
re-paste (running it twice never duplicates), and `rollback.js.txt` requires
per-list confirmation before every delete. Do not seed a
site that already holds real measures.

## After the paste: verification checklist

- [ ] `MR_Measure` exists and all five declared views appear: **The
      catalogue** (the default), **By forum**, **Definition reviews due**,
      **In development**, **Retired**. If you seeded, none of them is
      empty. The generated **All Items** recovery view is hidden from the
      modern view bar because this template has an authored default.
- [ ] **The catalogue** groups by `MeasureArea` with the groups expanded,
      and shows Active measures only.
- [ ] **By forum** groups by `ReportedTo` with the groups collapsed, so the
      first thing you see is the list of forums rather than the list of
      measures. Retired measures are absent.
- [ ] **Definition reviews due** shows Active measures whose `Next Review
      Due` falls within 60 days, oldest first, with `Last Reviewed Date`
      beside it. On the seeded build the overdue one sorts to the top and
      its due date carries the red overdue treatment.
- [ ] **`Next Review Due` is calculated and cannot be typed.** Open any
      measure for edit: the field is read-only and reads exactly twelve
      months after `Last Reviewed Date`. Move `Last Reviewed Date` back a
      month and the due date moves back a month with it. That is the point
      of the split: a review cannot be pushed out without claiming a review
      that did not happen.
- [ ] **The month end clamps.** Set `Last Reviewed Date` to 31 August and
      `Next Review Due` reads 28 February (29 in a leap year), not 3 March.
- [ ] **Retired** shows the retired measure with its `Last Reviewed Date`
      and no due date at all. A retired measure's definition is history,
      kept so old reports can be read, so the formula returns blank rather
      than a date that keeps shouting after retirement.
- [ ] List Settings -> Indexed columns shows `Status`, `MeasureArea` and
      `Frequency`. The build manifest lists the same three.
- [ ] The New form shows four sections in order: **Name the measure**,
      **Define it**, **Report it**, **Govern it**. Each holds the fields
      named in `20-configure/formatting/measure-form-body.json`. There is
      no **System** section. This list stamps nothing automatically, so
      shipping an empty heading would be worse than collapsing the beat.
- [ ] `Definition`, `DataSource` and `ReportedTo` are **required** (the
      form refuses a measure without them, deliberate).
- [ ] Nothing on this form appears or disappears as you fill it in. That is
      correct: no column here is conditional on another, so no
      `form_visibility` is declared and none is deployed.
- [ ] **The two save rules.** Set `Status` to **Active** and clear `Last
      Reviewed Date`: the save is refused, naming the last reviewed date.
      Then set a last reviewed date in the **future**: refused again, with
      its own message, because that rule reads only its own column and so
      keeps its own wording. Leave the date blank on an **Under
      development** measure and it saves: the list rule requires it of
      Active measures only.
- [ ] **Load the current KPIs**: everything on today's dashboards and
      committee packs goes in now, including (especially) the ones whose
      definitions turn out to be folklore when someone tries to write them
      down. Expect that step to be the most valuable meeting of the
      quarter.
- [ ] As an ordinary Member: read-only.
- [ ] Populate **MR Measure Custodians**; delete any test rows.
- [ ] Even as an owner: changing a deployed column's type, choices or
      settings is refused (sealed) and List settings offers no "Delete
      this list"; a display-name rename is still possible: it is
      drift, reverted and reported at the next re-paste.

## Redeploying

Bump `schema_version`, rebuild, re-paste. The five declared views are
reconciled every run; views you create yourself are user content and are
never touched.

### Coming from 1.0.x: transferring Review Date

1.1.0 splits `ReviewDate` into `Last Reviewed Date` and a calculated `Next
Review Due`. The old column is **retired, not deleted**: it keeps its values,
drops off every view and the New form, and reads `Review Date (retired)`.

The two dates do not mean the same thing, so this is not a copy. `ReviewDate`
held the *next* review; `Last Reviewed Date` holds the *last* one, and nobody
recorded it. For each Active measure, set `Last Reviewed Date` to the date the
definition was actually last re-tested. Where nobody knows, `ReviewDate` minus
twelve months is the honest reconstruction of what the old column was
asserting, and it lands the row in the same place in the review queue.

Once every row is transferred, run the columns sidecar on `MR_Measure` to
delete `ReviewDate`, plus anything else its table shows that the schema no
longer declares.

## Enterprise reporting access

The deploy declares the `dbml Enterprise Readers` site group, shared with every
other family deployed to the site, and grants it `Read` on every list in this
family. The group starts empty only if no family has deployed to the site yet;
it gains a member when any family's build is run with `--enterprise-reader
<account>`, which enrols exactly that one account and nothing else.
`rollback.js.txt` does not remove it: rollback deletes lists, not site groups
or role assignments, so the group and any account enrolled in it survive a
rollback.

A later build that omits the flag does not put the group back to empty:
enrolment only runs when `--enterprise-reader` is given, so an account enrolled
by an earlier build (of this family or any other sharing the site) keeps its
membership and its `Read` grant on every list it was declared against. Removing
it is manual: clear it in Site permissions > Groups.

If the group already holds anyone other than that account, the deploy
**aborts before enrolling** and removes nobody. Before you clear anyone out,
check who it is: the group is shared by every family on this site, so the
unexpected member is most likely **another family's reporting account**, and
removing it silently breaks that family's reporting. Agree one reader account
for the site and rebuild with that address, or rebuild without the flag. Only
clear the group in Site permissions > Groups once you know nothing else needs
the account.

On one Microsoft 365 group-connected Team Site (measured 2026-08-11) the
enrolled account ends up with the built-in `Read` on each list and
`Use Remote Interfaces` intact at web scope. Publishing sites (where
lockdown mode is on by default) and the reporting client's own list
enumeration are still unverified, so the end-to-end path (Power BI or any
other API client) is not yet proven. See the danger block in the mapping
reference's Security section.
