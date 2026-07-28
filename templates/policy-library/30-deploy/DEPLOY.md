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
- [ ] **Set Draft Item Security — the deploy does not.** Library settings →
      Versioning settings → *Draft Item Security* → **"Only users who can
      edit"** → OK. SharePoint's default is "Any user who can read items",
      and nothing in `mapping.yaml` changes it: minor versioning and draft
      visibility are independent properties, and the deployer only writes
      the first. Skip this and every draft is readable by every staff
      member, which is the opposite of what this template is for.
- [ ] As an ordinary Member: both are read-only, and — **after** the step
      above — the library shows only the **published** (major) version of
      your test file, not the 0.1 draft. Check this as a Member, not as
      yourself; an author sees drafts either way.
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
