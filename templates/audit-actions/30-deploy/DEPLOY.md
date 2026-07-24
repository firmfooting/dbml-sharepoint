# Deploying audit actions (administrator)

Shared procedure: [`templates/README.md`](../../README.md) with
`<name> = audit-actions`. Template-specific notes below.

## Before you build

- [ ] `AU_` prefix free on the target site.
- [ ] `AuditType`/`FindingRating` enums match your assurance framework
      (many audit firms rate findings themselves — mirror their scale).
- [ ] You know who forms **AU Audit Coordinators**.

## After the paste — verification checklist

- [ ] `AU_Audit` and `AU_Recommendation` exist (Audit first).
- [ ] Create a test audit, then a recommendation against it (the Audit
      lookup offers it); AgreedAction/Owner/DueDate are required.
- [ ] DaysLate spot-checks: Due `2026-07-01` + Closed `2026-07-10` → **9**;
      Closed `2026-06-28` (early) → **0**; add RevisedDue `2026-07-15`,
      Closed `2026-07-20` → **5**.
- [ ] Ordinary Members: read-only.
- [ ] **Load the backlog**: every open recommendation from existing audits
      goes in now — a partial register is worse than none, because it looks
      complete.
- [ ] Populate **AU Audit Coordinators**; delete the test rows.
- [ ] Even as an owner: changing a deployed column's type, choices or
      settings is refused (sealed) and List settings offers no "Delete
      this list"; a display-name rename is still possible — it is
      drift, reverted and reported at the next re-paste.

## Recommended views

| List | View | Filter / grouping |
|---|---|---|
| Recommendation | Open by owner | Status ≠ Closed/Risk accepted, group by Owner |
| Recommendation | Overdue | Status ≠ Closed/Risk accepted, (RevisedDue or DueDate) < today |
| Recommendation | Committee pack | Status ≠ Closed, group by Audit, sorted by FindingRating |
| Recommendation | Closed this quarter | ClosedDate in range, show DaysLate + EvidenceUrl |

## Redeploying

Bump `schema_version`, rebuild, re-paste.
