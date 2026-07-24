# Deploying the asset register (administrator)

Shared procedure: [`templates/README.md`](../../README.md) with
`<name> = asset-register`. Template-specific notes below.

## Before you build

- [ ] `AS_` prefix free on the target site.
- [ ] `Category`/`Status` choices match how you actually classify equipment.
- [ ] Decide the Members-can-edit question (see template README) — change
      the Members assignment to `Read` plus a custodians group *before*
      first deploy if you want the tighter model.

## After the paste — verification checklist

- [ ] `AS_Location` and `AS_Asset` exist, in that creation order.
- [ ] **Seed Locations first** — add your buildings/rooms/sites now; the
      Asset form's Location dropdown reads from it.
- [ ] Create a test asset: unique `AssetTag` enforced (try a duplicate —
      rejected); Purchase `2026-01-01` + Warranty `2028-01-01` →
      **WarrantyMonths = 24**.
- [ ] Assign it to yourself (`AssignedTo`), set Status `Assigned`.
- [ ] Delete the test asset.
- [ ] Even as an owner: changing a deployed column's type, choices or
      settings is refused (sealed) and List settings offers no "Delete
      this list"; a display-name rename is still possible — it is
      drift, reverted and reported at the next re-paste.

## Recommended views

| View | Filter / grouping |
|---|---|
| By holder | Group by `AssignedTo`, Status = Assigned |
| By location | Group by `Location` |
| Warranty expiring | `WarrantyExpiry` ≤ today+60 |
| Stocktake sheet | All in-service/assigned, sorted by Location then AssetTag |

## Redeploying

Bump `schema_version` in `release.yaml`, rebuild, re-paste. Existing rows
untouched; declared settings reconciled.
