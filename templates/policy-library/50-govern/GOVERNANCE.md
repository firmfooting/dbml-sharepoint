# Policy library — governance

## Ownership

| Role | Held by | Accountable for |
|---|---|---|
| Framework owner | *(e.g. governance/quality lead)* | The register's completeness, review discipline, this document |
| Policy owner (per row) | The register `Owner` | That policy's currency and review |
| PL Policy Authors | The authoring group | Drafting, publishing, register upkeep |

## Review discipline

- **Monthly**: framework owner works the *Review due* view — it deploys
  with the register, filtered to published policies due inside a
  **rolling** ninety days (CAML has no calendar-period predicate, so it is
  ninety days from whenever you open it, not "this quarter"). Every policy
  in it gets a named reviewer and a target date. Then the *In development*
  view: anything sitting at **Approved** is a decision staff cannot yet
  read, and it renders amber for that reason.
- **A review is real when**: the document was re-read against current
  practice/legislation, changes were made or explicitly declined, the
  approval is recorded in Notes, and ApprovedDate/ReviewDate move.
- **Standard interval**: 24 months (36 for low-risk areas) — set per policy
  via ReviewDate; the calculated ReviewMonths makes outliers visible. It
  now renders as a bar scaled to **36 months**, the ceiling this table
  names, so anything pinning it full is by definition an outlier. **If you
  change the interval above, change that `max` in
  `20-configure/mapping.yaml` to match** — a bar scaled to somebody else's
  interval means nothing.

## Approval rules (edit to your delegations)

| Policy area | Approved by |
|---|---|
| Governance | Board / executive |
| People, Finance, Operations, IT, H&S | Accountable executive for the area |

Record the actual approver and date in the register row's Notes every time.

## Register ↔ library sync rules

1. Every **published** document has a register row pointing at it, and vice
   versa — the monthly review includes a five-minute orphan check both ways.
2. `Status` in the register and `Document Status` on the document agree;
   the register wins disputes.
3. Supersession: old policy's row → Status **Superseded**, Notes name the
   successor; the document stays (history), the register link moves.

## What the register enforces, and what this document does

The register half of this template now refuses two things at save. The
library half refuses nothing, and the sync rules above cannot be enforced
at all.

**Enforced at save — SharePoint rejects the row:**

| Rule | Where it lives | Message shown |
|---|---|---|
| An *Approved* or *Published* policy needs an `ApprovedDate` | list validation | Names it as what the review interval is measured from |
| `ApprovedDate` cannot be in the future | column validation | Its own message, on the column |

The interval rule matters more than it looks. `ReviewMonths` is computed
from `ApprovedDate`, so a published policy without one leaves the outlier
check above with nothing to read — and a *future* approval date makes the
interval look shorter than it is and quietly moves the policy down the
list.

**Still a governance check — nothing stops a wrong entry:**

- **Sync rule 3's supersession trail.** `Notes` is rich text, which a
  validation formula cannot reference at all. The *Retired* view shows the
  column beside every superseded and withdrawn row so its absence is
  visible.
- **A published policy having a `DocumentUrl`.** It is a hyperlink column,
  and although this tool accepts a hyperlink operand in a validation
  formula (and `audit-actions` ships one), it has never been read back from
  a live tenant, so the rule is not written here. Both *By area* and
  *Review due* show the column.
- **Sync rules 1 and 2 entirely.** The register and the library are two
  lists with no link between them by design, and no formula spans two
  lists. The five-minute orphan check is the only control there is, which
  is why it is in the monthly cadence rather than in a checklist somebody
  reads once.
- **Approval authority.** Who may approve what is a delegation, not a
  formula — see the table above, and `delegations-register` if you run one.

**What the colours do.** *Approved* is amber, not green: the decision is
made and staff still cannot read the policy, which is a job half done and
should not look finished. *Withdrawn* renders differently from
*Superseded* on purpose — a superseded policy was replaced, a withdrawn one
was pulled with nothing in its place, and that is a hole in the framework
rather than a tidy substitution. `ReviewDate` turns red once past, and
stops on both retired statuses.

## Access rationale

Readers see only published majors **once *Draft Item Security* is set to
"Only users who can edit"** — draft visibility does *not* follow minor
versioning; it is a separate library property, SharePoint defaults it to
"Any user who can read items", and the deploy does not write it. That
one-time step is in `30-deploy/DEPLOY.md`, it survives redeploys, and it is
the log owner's to verify: without it the Read-level access below exposes
every unapproved draft. Authors contribute; schema rights confined to the
empty admin group. Approval authority is process, not permissions —
SharePoint doesn't enforce your delegations; this document does.

## Lifecycle

Withdrawn policies: Status **Withdrawn**, document retained per your records
schedule. Export the register before any decommission; never run
`rollback.js` against live policy data.
