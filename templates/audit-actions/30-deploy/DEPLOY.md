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
- [ ] **Form behaviour** (declared in `mapping.yaml` under
      `form_visibility:` — this is the one template that demonstrates it):
      on the *New* form, RevisedDue, ClosedDate and EvidenceUrl are all
      absent. Save the row, reopen it for edit: RevisedDue is now there;
      ClosedDate and EvidenceUrl are still hidden. Set Status to
      *Implemented - awaiting evidence* — EvidenceUrl appears as you
      change the value, without saving. Set it to *Closed* — ClosedDate
      appears too.
- [ ] **Closure needs a Closed Date** (`list_validation:`): with Status
      *Closed* and ClosedDate empty, saving is refused with the declared
      message. Fill it; it saves.
- [ ] **EvidenceUrl is NOT enforced at save**, and confirm that rather
      than assume it: Status *Closed* with EvidenceUrl empty and a
      ClosedDate filled **saves**. SharePoint does not permit the
      alternative — a validation formula referencing a URL column is
      refused when you try to set it — so the build refuses the operand and
      evidence at closure stays a governance criterion.
- [ ] Hidden ≠ inaccessible. Confirm a hidden column still holds its value:
      the reporting bundle's data dictionary lists all three, and a view
      can show them. `form_visibility` governs forms only.
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
