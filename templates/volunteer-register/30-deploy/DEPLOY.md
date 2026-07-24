# Deploying the volunteer register (administrator)

Shared procedure: [`templates/README.md`](../../README.md) with
`<name> = volunteer-register`. Template-specific notes below.

## Before you build

- [ ] `VL_` prefix free on the target site.
- [ ] **Privacy check**: site membership = volunteer coordinators + owners
      only (ordinary members get no grant by design; the site audience
      should match).
- [ ] Check names match your jurisdiction (WWCC / Blue Card / WWVP —
      rename the columns in the DBML if yours differ) and the
      role-requirements matrix in `50-govern/GOVERNANCE.md` is agreed.

## After the paste — verification checklist

- [ ] `VL_Volunteer` exists; `VolunteerRole` and `Coordinator` required.
- [ ] As an ordinary Member: **cannot see the list**.
- [ ] As a Coordinator: full create/edit.
- [ ] **Load current volunteers** — including the drawer of paper: every
      active volunteer with their real check expiry dates (this load is
      where most programmes discover their first expired check — that's
      the register working on day one).
- [ ] Populate **VL Volunteer Coordinators**; delete any test rows.
- [ ] Even as an owner: changing a deployed column's type, choices or
      settings is refused (sealed) and List settings offers no "Delete
      this list"; a display-name rename is still possible — it is
      drift, reverted and reported at the next re-paste.

## Recommended views

| View | Filter / grouping |
|---|---|
| Active by team | Status = Active, group by Team |
| Checks expiring 90 days | Status = Active, PoliceCheckExpiry or WWCCExpiry ≤ today+90 |
| Missing checks | Status = Active and a required check column blank (per the role matrix) |
| Pipeline | Status = Applying — the onboarding queue |

## Redeploying

Bump `schema_version`, rebuild, re-paste.
