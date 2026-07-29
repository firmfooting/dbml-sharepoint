# Asset register — governance

## Ownership

| Role | Held by | Accountable for |
|---|---|---|
| Register owner | *(e.g. IT manager / facilities manager)* | Register completeness, stocktakes, this document |
| Every staff member | — | Updating rows for equipment they issue/receive |
| Site Owners | IT / site admins | Group membership, deploys |

## Stocktake cadence

- **Quarterly**: reconcile the **Stocktake** view against reality for
  one location (rotate locations so each is covered yearly). It sorts by
  Location then Asset Tag, which is the order you physically walk.
  Record variances in the row's Notes.
- **On every leaver**: the **By holder** view is the exit checklist —
  their group is empty before the leaver's account is disabled.
- **Every 60 days**: the **Warranty expiring** view. A claim missed
  because nobody knew the purchase date is the cheapest loss in this
  register to prevent.
- **Annually**: review the **Retired and disposed** view — anything to
  dispose, dispose and mark; confirm PurchaseCost totals reconcile roughly
  with the asset ledger if finance keeps one.

## What is enforced at save, and what stays a governance check

| Enforced at save | Rule |
|---|---|
| `Asset Tag` | Unique across the register (a schema constraint, not a formula) |
| `Purchase Date` | Cannot be in the future |
| `Purchase Cost` | Cannot be negative |
| The list | An asset with a Warranty Expiry must also have a Purchase Date |

Data-quality rule 2 below — *AssignedTo blank ⇒ Status must not be
Assigned, and vice versa* — reads like the obvious save rule and **cannot
be one**. SharePoint validation formulas cannot reference person columns
at all, in either direction: not as an operand, not as a null test. What
the register does instead is structural: **Assigned To disappears from the
form once an item is Retired or Disposed**, which stops the commonest half
of the problem (equipment disposed while still assigned to someone who
left). The other half — an item marked Assigned with nobody named — is
caught by the *By holder* view, where it simply does not appear.

Rule 1, that the tag mirrors the physical sticker exactly, is a habit.
Uniqueness is enforced; honesty is not.

## Data-quality rules

1. `AssetTag` is the identity — it mirrors the physical tag exactly, no
   "spare"/"old" suffixes.
2. `AssignedTo` blank ⇒ Status must not be `Assigned` (and vice versa).
   **Not enforceable — see above.**
3. `Disposed` rows keep their history and their Notes say how and when
   disposed.

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
