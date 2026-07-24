# Deploying the training register (administrator)

Shared procedure: [`templates/README.md`](../../README.md) with
`<name> = training-register`. Template-specific notes below.

## Before you build

- [ ] `TR_` prefix free on the target site.
- [ ] `Category` enum matches your training framework.
- [ ] You know who forms **TR Training Coordinators**.

## After the paste — verification checklist

- [ ] `TR_Course` and `TR_TrainingRecord` exist, catalogue created first.
- [ ] **Seed the catalogue** — enter your required courses/certifications
      with their `ValidityMonths` before any records; the record form's
      Course dropdown reads from it.
- [ ] Create a test record against a course: Person = you, CompletedDate
      today, ExpiryDate per the course validity; the Course lookup offers
      the seeded catalogue.
- [ ] As an ordinary Member: both lists read-only.
- [ ] Populate **TR Training Coordinators**; delete the test record.
- [ ] Even as an owner: changing a deployed column's type, choices or
      settings is refused (sealed) and List settings offers no "Delete
      this list"; a display-name rename is still possible — it is
      drift, reverted and reported at the next re-paste.

## Recommended views

| List | View | Filter |
|---|---|---|
| TrainingRecord | Expiring 60 days | Status ≠ Expired/Not required, ExpiryDate ≤ today+60 |
| TrainingRecord | By person | Group by Person |
| TrainingRecord | By course | Group by Course, Status = Current |
| Course | Mandatory catalogue | Mandatory = Yes |

## Note on expiry status

`Status` is **not** self-updating — SharePoint calculated columns cannot
reference "today", so the template deliberately leaves status maintenance to
the coordinators' weekly sweep (see `50-govern/GOVERNANCE.md`) or to a small
scheduled automation you add later. The `ExpiryDate` index keeps either
approach a single cheap filtered query.

## Redeploying

Bump `schema_version`, rebuild, re-paste. Rows untouched; settings
reconciled.
