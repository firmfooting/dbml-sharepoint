# Deploying incident management (administrator)

Shared procedure: [`templates/README.md`](../../README.md) with
`<name> = incident-management`. Template-specific notes below.

## Before you build

- [ ] `IN_` prefix free on the target site.
- [ ] `Severity` and `Category` enums match your incident taxonomy — the
      governance doc's severity definitions must agree with the choices.
- [ ] You know who forms **IN Incident Handlers**.

## After the paste — verification checklist

- [ ] `IN_Incident` and `IN_CorrectiveAction` exist; the custom permission
      level **IN Report Only** exists (Site settings → Site permissions →
      Permission levels).
- [ ] As an ordinary Member: you can **New** an incident but the saved row
      shows no Edit for you — and you cannot edit anyone else's.
- [ ] As a Handler: you can edit the test incident, set `Handler`, and add
      a linked corrective action (the Incident lookup offers the test row).
- [ ] Set ReportedDate `2026-07-01`, ResolvedDate `2026-07-08` →
      **DaysToResolve = 7**.
- [ ] Populate **IN Incident Handlers**; delete the test rows (as Handler).
- [ ] Even as an owner: changing a deployed column's type, choices or
      settings is refused (sealed) and List settings offers no "Delete
      this list"; a display-name rename is still possible — it is
      drift, reverted and reported at the next re-paste.

## Recommended views

| List | View | Filter |
|---|---|---|
| Incident | Triage queue | Status = Reported, sorted oldest first |
| Incident | Open by severity | Status ≠ Resolved/Closed, group by Severity |
| CorrectiveAction | Overdue | Status ≠ Done/Cancelled and DueDate < today |

## Redeploying

Bump `schema_version`, rebuild, re-paste. The report-only level's
permissions are reconciled on every run — drift is corrected, not accepted.
