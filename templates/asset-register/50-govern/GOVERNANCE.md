# Asset register — governance

## Ownership

| Role | Held by | Accountable for |
|---|---|---|
| Register owner | *(e.g. IT manager / facilities manager)* | Register completeness, stocktakes, this document |
| Every staff member | — | Updating rows for equipment they issue/receive |
| Site Owners | IT / site admins | Group membership, deploys |

## Stocktake cadence

- **Quarterly**: reconcile the *Stocktake sheet* view against reality for
  one location (rotate locations so each is covered yearly). Record
  variances in the row's Notes.
- **On every leaver**: the *By holder* view is the exit checklist — zero
  assigned rows before the leaver's account is disabled.
- **Annually**: review `Retired` rows — anything to dispose, dispose and
  mark; confirm PurchaseCost totals reconcile roughly with the asset ledger
  if finance keeps one.

## Data-quality rules

1. `AssetTag` is the identity — it mirrors the physical tag exactly, no
   "spare"/"old" suffixes.
2. `AssignedTo` blank ⇒ Status must not be `Assigned` (and vice versa).
3. `Disposed` rows keep their history and their Notes say how/when disposed.

## Access rationale

Everyone contributes because everyone touches equipment; nobody can change
the list structure (Full Control confined to the empty admin group the
deploy script uses). If shrinkage or misuse becomes an issue, tighten
Members to Read and route changes through a custodians group — a one-line
mapping change and redeploy.

## Lifecycle

- Financial depreciation lives in the finance system; this register is the
  operational truth that feeds it.
- Decommissioning: export to Excel first; never run `rollback.js` against a
  populated register.
