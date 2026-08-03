# Deploying the vehicle log (administrator)

Shared procedure: [`templates/README.md`](../../README.md) with
`<name> = vehicle-log`. Run order: **assess** the target site (paste
`build/assess.js.txt`, read-only; the verdict must be COMPATIBLE or an accepted
DEGRADED) → **review** `build/deploy-manifest.md` (must show 0 validation
errors) → **paste** `build/deploy.js.txt` from a Site Owner's console →
**verify** against the checklist below. Template-specific notes follow.

## Before you build

- [ ] `VE_` prefix free on the target site.
- [ ] The private/commute-use policy decision is made (governance) — if
      private use is never permitted, delete those `TripType` values from
      the enum before first deploy. They are named in the deployed
      formatter map, so the build will refuse a stale name there rather
      than let it rot.
- [ ] Paper log books have a cutover date; finance knows the digital log
      becomes the substantiation record from that date.
- [ ] The Trip header shows `Trip: <title>` on a titled trip and just
      `Trip` on an untitled one — **not** "New trip". Title is optional
      here, because a trip is identified by its vehicle and its time, so
      an empty Title does not mean the row is new.

## Optional: the seeded demonstration build

Odometer continuity, the negative-kilometre row wash and three of the four
Trip views are invisible on an empty pair of lists. To see them working,
rebuild with `--seed`:

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
first, then `demo-data.js.txt`, from the same bundle. It creates four vehicles
and six trips. The odometer readings run **continuously per vehicle** —
each trip starts where the last one finished — because that continuity is
what a fleet owner reads this register for. One deliberate exception: the
van's depot run has its two readings transposed, which produces a negative
Trip km and is what the row wash exists to make obvious.

**Delete the demo rows before active use.** Every demo Title begins with
`[DEMO] `, so they are obvious in every view, they are matched by Title on
re-paste (running it twice never duplicates), and `rollback.js.txt` treats a
list whose rows are *all* demo-marked as demo-only content. Do not seed a
site that already holds real trips.

## After the paste — verification checklist

- [ ] `VE_Vehicle` and `VE_Trip` exist (Vehicle first); `Rego` rejects a
      duplicate.
- [ ] `VE_Vehicle` has **The fleet** (the default) and **In workshop**.
      `VE_Trip` has **Out now** (the default), **By vehicle**, **My
      trips** and **Last 30 days by vehicle**. If you seeded, none is
      empty. The generated **All Items** recovery view is hidden from the
      modern view bar on both lists.
- [ ] **What replaced the old recommended-views table**, since two of its
      four rows could not be built as written:
      - **"Per vehicle"** asked for a view filtered to one vehicle.
        SharePoint has no per-parent filter, so building it meant either
        hard-coding one car into a filter that rots the next time the
        fleet changes, or maintaining one view per car. It ships as **By
        vehicle** — one view grouped on the Vehicle lookup, collapsed,
        which is the real idiom, gives the same continuous log book, and
        absorbs a new car with no work.
      - **"Monthly km by vehicle"** asked for trips in a calendar month,
        grouped by vehicle, with `TripKm` **summed**. The sum is there:
        the view groups by vehicle and collapses, so SharePoint shows a
        kilometre total under each vehicle and one for the whole window —
        the fleet-review figure. Only the calendar half was substituted:
        CAML has no calendar-month predicate, so **Last 30 days by
        vehicle** is a rolling window and its title says so. For a
        financial-year or true calendar-month figure, still export.
- [ ] **My trips** shows only your own trips, and shows a colleague only
      theirs. It uses SharePoint's own current-user filter — one view for
      everybody, not one per driver.
- [ ] Test trip: OdoStart `45210`, OdoEnd `45274` → **Trip km = 64**, drawn
      as a bar against a 200 km scale. Swap them → **−64**, and in the **By
      vehicle** view the whole row washes dusty rose. That wash is the one
      row-level signal this template gets, and it is on that view because
      that is where odometer continuity is read.
- [ ] `Purpose`, `Driver`, `Vehicle`, `DepartedAt` and `Odometer Start`
      are required.
- [ ] The Trip New form shows three sections — **The trip**, **Out and
      back**, **System**. **Returned At** and **Odometer End** are absent
      from it: a trip is recorded in two halves, thirty seconds each end,
      and the New form asks only for the half a driver can answer at the
      key cupboard. Both appear on the Edit form, which is what *Out now*
      is for. **System** holds only the calculated `Trip km`, so on the
      New form it renders as a bare heading — cosmetic and expected.
- [ ] In any view, a trip with no **Returned At** shows an "Out now" chip
      in that column rather than an empty cell. Fill the field in and it
      becomes the time the car came back.
- [ ] Save rules, each with its own message: a **Departed At** in the
      future is refused, and so is a negative odometer reading on either
      side. The list rule refuses a trip that has a **Returned At** but no
      **Odometer End** — without it, Trip km is blank and the next trip's
      opening reading has nothing to reconcile against.
- [ ] One rule this register obviously wants is **not** enforced and
      cannot be: that the closing odometer exceeds the opening one. That
      is a column-to-column comparison, and the condition grammar this
      template is written in compares a column to a literal only. The
      negative Trip km and its row wash are the compensating control —
      loud rather than prevented. `50-govern/governance.md` says so.
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

## Redeploying

Bump `schema_version`, rebuild, re-paste.
