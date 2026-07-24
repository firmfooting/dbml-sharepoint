# Deploying the grants register (administrator)

Shared procedure: [`templates/README.md`](../../README.md) with
`<name> = grants-register`. Template-specific notes below.

## Before you build

- [ ] `GR_` prefix free on the target site.
- [ ] You know who forms **GR Grants Coordinators**.

## After the paste — verification checklist

- [ ] `GR_Submission` and `GR_Acquittal` exist (Submission first).
- [ ] Create a test submission; add an acquittal against it (the
      Submission lookup offers it; DueDate required).
- [ ] Ordinary Members: read-only.
- [ ] **Load the live estate**: every current grant as a Successful
      submission, then — agreement in hand — every reporting/acquittal
      obligation it contains, with real due dates. This load is the
      whole point; expect it to surface at least one obligation nobody
      was tracking.
- [ ] Populate **GR Grants Coordinators**; delete the test rows.
- [ ] Even as an owner: changing a deployed column's type, choices or
      settings is refused (sealed) and List settings offers no "Delete
      this list"; a display-name rename is still possible — it is
      drift, reverted and reported at the next re-paste.

## Recommended views

| List | View | Filter / sort |
|---|---|---|
| Acquittal | Due 90 days | AcqStatus = Upcoming/In preparation, DueDate ≤ today+90 — THE view |
| Acquittal | Overdue | AcqStatus = Overdue (set by the sweep) |
| Submission | Pipeline | Outcome = In preparation/Submitted, by DueDate |
| Submission | Live grants | Outcome = Successful, ProjectEndDate ≥ today |
| Submission | By funder | Group by Funder — the relationship history |

## Redeploying

Bump `schema_version`, rebuild, re-paste.
