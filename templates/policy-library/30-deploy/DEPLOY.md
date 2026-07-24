# Deploying the policy library (administrator)

Shared procedure: [`templates/README.md`](../../README.md) with
`<name> = policy-library`. Template-specific notes below.

## Before you build

- [ ] `PL_` prefix free on the target site.
- [ ] `PolicyArea` enum matches your policy framework's domains.
- [ ] You know who forms **PL Policy Authors**.

## After the paste — verification checklist

- [ ] `PL_PolicyDocuments` (document **library**) and `PL_PolicyRegister`
      (list) both exist.
- [ ] Library versioning: Library settings → Versioning shows **major AND
      minor** versions enabled. Upload a test file → it lands as **0.1**
      (a draft); Publish it (… → More → Publish) → **1.0**.
- [ ] Register: create a test policy with ApprovedDate `2026-07-01` and
      ReviewDate `2028-07-01` → **ReviewMonths = 24**.
- [ ] As an ordinary Member: both are read-only, and the library shows only
      the **published** (major) version of your test file, not the 0.1
      draft.
- [ ] Populate **PL Policy Authors**; delete the test file and row.
- [ ] Even as an owner: changing a deployed column's type, choices or
      settings is refused (sealed) and List settings offers no "Delete
      this list"; a display-name rename is still possible — it is
      drift, reverted and reported at the next re-paste.

## Recommended views

| Where | View | Filter |
|---|---|---|
| Register | Review due | ReviewDate ≤ today+90, Status = Published |
| Register | By area | Group by PolicyArea |
| Library | Drafts in progress | DocStatus = Draft or In review |

## Redeploying

Bump `schema_version`, rebuild, re-paste. Files and rows are untouched;
declared settings (including the minor-versioning flag) are reconciled.
