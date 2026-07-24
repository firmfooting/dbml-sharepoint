# Deploying the declarations register (administrator)

Shared procedure: [`templates/README.md`](../../README.md) with
`<name> = declarations-register`. Template-specific notes below.

## Before you build

- [ ] `DR_` prefix free on the target site.
- [ ] Enums match your code of conduct's categories.
- [ ] **Visibility decision made** (see the note in `mapping.yaml`): open
      register (default — all site members read) vs confidential register
      (scope site membership to the compliance function). Record the choice
      in `50-govern/GOVERNANCE.md`.
- [ ] Gift value thresholds agreed and written into governance.

## After the paste — verification checklist

- [ ] `DR_Interest` and `DR_GiftBenefit` both exist; custom level
      **DR Declare Only** exists.
- [ ] As an ordinary Member: you can submit a declaration to each list but
      cannot edit it afterwards.
- [ ] As a Coordinator: you can assess (Status/ManagementPlan on Interest;
      Decision/DecisionBy on GiftBenefit).
- [ ] The two lists are fully independent — no lookups between them.
- [ ] Populate **DR Compliance Coordinators**; delete the test rows.
- [ ] Even as an owner: changing a deployed column's type, choices or
      settings is refused (sealed) and List settings offers no "Delete
      this list"; a display-name rename is still possible — it is
      drift, reverted and reported at the next re-paste.

## Recommended views

| List | View | Filter / grouping |
|---|---|---|
| Interest | Live interests | Status ≠ Ceased, group by DeclaredBy |
| Interest | Reviews due | Status = Assessed - managed, ReviewDate ≤ today+30 |
| GiftBenefit | Pending decisions | Decision = Pending decision, oldest first |
| GiftBenefit | Annual disclosure | OfferedDate in year, sorted by EstimatedValue desc |

## Redeploying

Bump `schema_version`, rebuild, re-paste.
