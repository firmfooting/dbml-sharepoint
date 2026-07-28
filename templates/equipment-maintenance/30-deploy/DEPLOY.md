# Deploying equipment maintenance (administrator)

Shared procedure: [`templates/README.md`](../../README.md) with
`<name> = equipment-maintenance`. Template-specific notes below.

## Before you build

- [ ] `EM_` prefix free on the target site.
- [ ] `EquipmentType` enum covers your maintained classes; frequency
      defaults per class agreed in `50-govern/GOVERNANCE.md`.
- [ ] If you also run the **asset-register** template: decide the boundary
      now — asset-register owns *what/where/whose*; this owns *is it in
      test*. Same physical tag string in both keeps them joinable by eye.

## After the paste — verification checklist

- [ ] `EM_Equipment` and `EM_MaintenanceEvent` exist (Equipment first).
- [ ] Create a test item (unique `EquipmentTag` enforced — try a
      duplicate); record an event against it (Equipment lookup offers it;
      PerformedBy and Result required).
- [ ] As an ordinary Member: read-only.
- [ ] **Load the schedule** — every maintained item with its real
      NextDueDate (from the current binder/contractor list). An item not
      in the register is an item not in the schedule.
- [ ] Populate **EM Maintenance Team**; delete the test rows.
- [ ] Even as an owner: changing a deployed column's type, choices or
      settings is refused (sealed) and List settings offers no "Delete
      this list"; a display-name rename is still possible — it is
      drift, reverted and reported at the next re-paste.

## Recommended views

| List | View | Filter / sort |
|---|---|---|
| Equipment | Overdue | NextDueDate < today, Status = `In service` — THE view; empty is the goal |
| Equipment | Due 60 days | NextDueDate ≤ today+60, sorted ascending — the work plan |
| Equipment | Out of service | Status = `Out of service - awaiting maintenance` — reviewed daily |
| MaintenanceEvent | Failures | Result = `Failed - removed from service`, newest first |
| MaintenanceEvent | Per item | Filter by Equipment — the service history an auditor reads |

## Redeploying

Bump `schema_version`, rebuild, re-paste.
