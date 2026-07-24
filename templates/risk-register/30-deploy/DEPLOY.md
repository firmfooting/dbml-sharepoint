# Deploying the risk register (administrator)

Shared procedure: [`templates/README.md`](../../README.md) with
`<name> = risk-register`. Template-specific notes below.

## Before you build

- [ ] `RR_` prefix free on the target site.
- [ ] `Category` enum matches your risk taxonomy.
- [ ] If your organisation has its OWN risk matrix, encode it in
      `mapping.yaml` **now**, before first deploy — the matrix comment shows
      the cell layout; keep the DBML likelihood/consequence enums in the
      same order as the formula indexes.

## After the paste — verification checklist

- [ ] `RR_Risk` exists; `RiskRating` and `RiskScore` columns present.
- [ ] Matrix spot-checks on a test risk:
      - Rare + Insignificant → **Low / 1**
      - Possible + Moderate → **Medium / 9**
      - Likely + Severe → **Extreme / 20**
      - Clear Likelihood → both go **blank** (unrated is visible, not
        defaulted).
- [ ] Neither calculated column is editable in the form.
- [ ] As an ordinary Member: read-only.
- [ ] Populate **RR Risk Managers**; delete the test risk.
- [ ] Even as an owner: changing a deployed column's type, choices or
      settings is refused (sealed) and List settings offers no "Delete
      this list"; a display-name rename is still possible — it is
      drift, reverted and reported at the next re-paste.

## Recommended views

| View | Filter / sort |
|---|---|
| Heat list | Status ≠ Closed, sorted by RiskScore descending |
| Extreme & High | RiskRating = Extreme or High, Status ≠ Closed |
| Reviews overdue | ReviewDate < today, Status ≠ Closed |
| By category | Group by Category |

## Redeploying — matrix change warning

A redeploy applies formula changes to the live columns, and SharePoint then
**recalculates every existing row**. That is desirable for a typo fix and
dangerous for a matrix revision — follow the change-control steps in
`50-govern/GOVERNANCE.md` (export snapshot first) before any cell change.
