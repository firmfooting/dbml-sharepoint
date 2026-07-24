# Deploying the vehicle log (administrator)

Shared procedure: [`templates/README.md`](../../README.md) with
`<name> = vehicle-log`. Template-specific notes below.

## Before you build

- [ ] `VE_` prefix free on the target site.
- [ ] The private/commute-use policy decision is made (governance) — if
      private use is never permitted, delete those `TripType` values from
      the enum before first deploy.
- [ ] Paper log books have a cutover date; finance knows the digital log
      becomes the substantiation record from that date.

## After the paste — verification checklist

- [ ] `VE_Vehicle` and `VE_Trip` exist (Vehicle first); `Rego` rejects a
      duplicate.
- [ ] Test trip: OdoStart `45210`, OdoEnd `45274` → **TripKm = 64**;
      swap them → **−64** shows (the visible-error design — fix the
      readings, per the schema note).
- [ ] `Purpose`, `Driver`, `DepartedAt`, `OdoStart` are required.
- [ ] Any Member can record trips.
- [ ] **Load the fleet** with current odometer readings as each vehicle's
      first trip anchor.
- [ ] QR code to the Trip New-form on each key tag or sun visor — the
      glovebox is where adoption happens.
- [ ] Delete the test rows.
- [ ] Even as an owner: changing a deployed column's type, choices or
      settings is refused (sealed) and List settings offers no "Delete
      this list"; a display-name rename is still possible — it is
      drift, reverted and reported at the next re-paste.

## Recommended views

| View | Filter / grouping |
|---|---|
| Out now | ReturnedAt empty — who has which car |
| Per vehicle | Filter by Vehicle, sorted by DepartedAt — the log book, continuous |
| My trips | Driver = [Me] |
| Monthly km by vehicle | DepartedAt in month, group by Vehicle, sum TripKm — fleet review + FBT feed |

## Redeploying

Bump `schema_version`, rebuild, re-paste.
