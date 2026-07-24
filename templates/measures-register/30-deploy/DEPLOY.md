# Deploying the measures register (administrator)

Shared procedure: [`templates/README.md`](../../README.md) with
`<name> = measures-register`. Template-specific notes below.

## Before you build

- [ ] `MR_` prefix free on the target site.
- [ ] You know who forms **MR Measure Custodians** (small — definitions
      need guarding, not committees).

## After the paste — verification checklist

- [ ] `MR_Measure` exists; `Definition`, `DataSource`, `ReportedTo` are
      **required** (the form refuses a measure without them — deliberate).
- [ ] As an ordinary Member: read-only.
- [ ] **Load the current KPIs**: everything on today's dashboards and
      committee packs goes in now — including (especially) the ones whose
      definitions turn out to be folklore when someone tries to write them
      down. Expect that step to be the most valuable meeting of the
      quarter.
- [ ] Populate **MR Measure Custodians**; delete any test rows.
- [ ] Even as an owner: changing a deployed column's type, choices or
      settings is refused (sealed) and List settings offers no "Delete
      this list"; a display-name rename is still possible — it is
      drift, reverted and reported at the next re-paste.

## Recommended views

| View | Filter / grouping |
|---|---|
| The catalogue | Status = Active, group by MeasureArea |
| By forum | Group by ReportedTo — what each committee actually sees |
| Definition reviews due | ReviewDate ≤ today+60, Status = Active |
| In development | Status = Under development |

## Redeploying

Bump `schema_version`, rebuild, re-paste.
