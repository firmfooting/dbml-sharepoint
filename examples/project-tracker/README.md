# Example: Project Tracker

Three linked lists — `PT_Project`, `PT_Task`, `PT_TimeLog` — exercising most
of what dbml-sharepoint supports:

| Feature | Where |
|---|---|
| Every scalar type (text, note, choice, person, date, number, boolean, hyperlink) | `Project` |
| Choice enums with defaults | `Status`, `Priority` |
| Unique column | `Project.Code` |
| Same-site Lookup chain | `TimeLog.Task → Task.Project → Project` |
| Self-lookup (deferred to Phase 2 automatically) | `Task.ParentTask` |
| Calculated column (formula in the mapping) | `Project.BudgetHealth` |
| Optional Title (patched non-required) | `TimeLog.Title` |
| Indexes + per-list versioning override | `mapping.yaml` |
| Groups, operator self-enrolment, exact-allowlist ACLs | `mapping.yaml` |

## Build

```bash
dbml-sharepoint build \
  --schema schema.dbml \
  --mapping mapping.yaml \
  --release release.yaml \
  --site-url https://yourtenant.sharepoint.com/sites/your-site \
  --site-role default \
  --out ./build
```

## Deploy

Open `build/deploy-manifest.md` and follow its "How to run this deployment"
section: it must show **0 validation errors**, then you paste `build/deploy.js`
into the browser console on a classic page of the target site
(`/_layouts/15/settings.aspx`), signed in as a Site Owner.

## Try the interesting bits afterwards

- Create a Project with `Budget 1000` / `Spent 950` → `BudgetHealth` shows
  "At risk"; raise Spent past 1000 → "Over budget".
- Create a Task, then another Task with the first as `ParentTask` — the
  self-lookup was created in Phase 2.
- Check Site permissions → Groups: `PT List Administrators` exists, is empty,
  and holds Full Control on the three lists while Members hold Contribute.
- Paste `deploy.js` a second time: everything verifies and skips —
  the script is a reconciler, not a one-shot.
