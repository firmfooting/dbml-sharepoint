# Policy library — governance

## Ownership

| Role | Held by | Accountable for |
|---|---|---|
| Framework owner | *(e.g. governance/quality lead)* | The register's completeness, review discipline, this document |
| Policy owner (per row) | The register `Owner` | That policy's currency and review |
| PL Policy Authors | The authoring group | Drafting, publishing, register upkeep |

## Review discipline

- **Monthly**: framework owner works the *Review due* view; every policy
  inside its 90-day window gets a named reviewer and a target date.
- **A review is real when**: the document was re-read against current
  practice/legislation, changes were made or explicitly declined, the
  approval is recorded in Notes, and ApprovedDate/ReviewDate move.
- **Standard interval**: 24 months (36 for low-risk areas) — set per policy
  via ReviewDate; the calculated ReviewMonths makes outliers visible.

## Approval rules (edit to your delegations)

| Policy area | Approved by |
|---|---|
| Governance | Board / executive |
| People, Finance, Operations, IT, H&S | Accountable executive for the area |

Record the actual approver and date in the register row's Notes every time.

## Register ↔ library sync rules

1. Every **published** document has a register row pointing at it, and vice
   versa — the monthly review includes a five-minute orphan check both ways.
2. `Status` in the register and `DocStatus` on the document agree; the
   register wins disputes.
3. Supersession: old policy's row → Status **Superseded**, Notes name the
   successor; the document stays (history), the register link moves.

## Access rationale

Readers see only published majors (library draft-visibility follows minor
versioning); authors contribute; schema rights confined to the empty admin
group. Approval authority is process, not permissions — SharePoint doesn't
enforce your delegations; this document does.

## Lifecycle

Withdrawn policies: Status **Withdrawn**, document retained per your records
schedule. Export the register before any decommission; never run
`rollback.js` against live policy data.
