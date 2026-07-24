# Deploying the change register (administrator)

Shared procedure: [`templates/README.md`](../../README.md) with
`<name> = change-register`. Template-specific notes below.

## Before you build

- [ ] `CH_` prefix free on the target site.
- [ ] `ChangeType` choices cover what your organisation actually changes.
- [ ] The decision-authority table in `50-govern/GOVERNANCE.md` is agreed —
      the register records approvals; the table is what makes them mean
      something.

## After the paste — verification checklist

- [ ] `CH_ChangeRequest` exists; custom level **CH Submit Only** exists
      (Site settings → Permission levels).
- [ ] As an ordinary Member: you can submit a test request but not edit it
      afterwards, nor anyone else's.
- [ ] As a Change Manager: you can triage it (Impact, Approver, Status).
- [ ] RequestedDate `2026-07-01` + DecisionDate `2026-07-10` →
      **DaysToDecision = 9**.
- [ ] Populate **CH Change Managers**; delete the test row (as a manager).
- [ ] Even as an owner: changing a deployed column's type, choices or
      settings is refused (sealed) and List settings offers no "Delete
      this list"; a display-name rename is still possible — it is
      drift, reverted and reported at the next re-paste.

## Recommended views

| View | Filter / sort |
|---|---|
| Triage queue | Status = Submitted, oldest first |
| Awaiting decision | Status = Under review, group by Approver |
| Approved, not yet implemented | Status = Approved |
| Decision log | Status = Approved/Rejected/Implemented/Closed, newest first |

## Redeploying

Bump `schema_version`, rebuild, re-paste. The submit-only level's
permissions are reconciled every run.
