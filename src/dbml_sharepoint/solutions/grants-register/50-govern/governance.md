# Grants register: governance

## Ownership

| Role | Held by | Accountable for |
| --- | --- | --- |
| Grants owner | *(e.g. CFO / business development lead)* | Bid/no-bid discipline, the sweep, funder relationships, this document |
| GR Grants Coordinators | The maintaining group | Pipeline and obligations upkeep |
| GrantOwner (per submission) | Named on the row | Delivery and every acquittal of that grant |

## Bid/no-bid discipline (ten minutes before any bid starts)

1. Does it fund something we already intend to do? (Grant-shaped mission
   drift is still mission drift.)
2. Can we deliver it with the people we actually have?
3. Do the obligations (read the *draft* agreement's reporting clauses
   now) cost less than the grant is worth?
4. Who is the GrantOwner? No owner, no bid.

Record the decision either way. Declined rounds inform next year.

## Acquittal escalation

- **Overdue** obligation: grants owner informed same day; contact the
  funder *proactively* within 2 business days (funders forgive early
  honesty far more than discovered silence); recovery date recorded in
  Notes.
- A second overdue on the same grant: the responsible executive is
  informed. The grant's delivery, not its paperwork, is now the question.

## Funder relationship hygiene

- *By funder* is the relationship file: every submission, outcome and
  acquittal in one view before any meeting with that funder.
- Unsuccessful-bid debriefs are mandatory (ProjectSummary). Patterns
  across them are the strategy input.

## Data-quality rules

1. No Successful submission without a linked agreement and its obligations
   loaded within a week of signing.
2. Every acquittal Submitted has a date and a filed, linked copy.
3. AmountAwarded comes from the agreement, not the announcement.

## What the lists enforce, and what this document does

Every one of those three rules is now **half** enforced, and the halves
that are missing are all the same shape: a hyperlink or a rich-text column,
neither of which a SharePoint validation formula can reach.

**Enforced at save (SharePoint rejects the row):**

| Rule | List | Where it lives |
| --- | --- | --- |
| Anything the funder has received (*Submitted*, *Successful*, *Unsuccessful*) needs a `SubmittedDate` | Submission | list validation |
| Rule 3: a *Successful* bid needs `AmountAwarded` | Submission | list validation |
| Rule 2, the date half: a filed obligation needs its `SubmittedDate` | Acquittal | list validation |
| `AmountSought` and `AmountAwarded` cannot be negative | Submission | column validation |
| A `SubmittedDate` cannot be in the future | both | list validation, hoisted from the column rule |

Each list has one `ValidationFormula`, so the two Submission rules share
one message naming both checks. SharePoint cannot say which branch failed.
The column rules keep messages of their own, which is why they say
something specific.

*Withdrawn* is exempt from the submitted-date rule: a bid can be withdrawn
before it is ever lodged, and question three of the bid/no-bid test above
is designed to produce exactly that outcome.

**Still a governance check (nothing stops a wrong entry):**

- **Rule 1's linked agreement** (`AgreementUrl`) and **rule 2's filed
  copy** (`EvidenceUrl`) are hyperlink columns. A validation formula has
  never been read back from a live tenant referencing one, and this
  library does not ship a rule it has not seen work. The *Live grants* and
  *Filed* views each show the link column so an empty one is visible in
  the sweep.
- **Rule 1's "within a week of signing".** Nothing on a submission row can
  know how many obligation rows point at it. This is the register's single
  most valuable habit and it is entirely on the coordinators, which is
  why 40-adopt gives it its own section rather than a bullet.
- **The unsuccessful-bid debrief.** `ProjectSummary` is rich text, which a
  validation formula cannot reference at all. *Lost bids* shows the column
  for that reason.
- **That `AmountAwarded` came from the agreement rather than the
  announcement.** A save rule proves a number is present. Only the
  quarterly reconciliation proves it is the right one.

**What the colours do, which is not enforcement but is the sweep's first
signal.** An `Overdue` obligation tints its whole row in *Open
obligations*, one row-level signal on the list, reserved for the one
state this document calls an incident. A *Submitted* obligation reads
amber rather than green, because it is still waiting on the funder's
acceptance; green is *Accepted by funder* and nothing else.

## Lifecycle

Grant records outlive projects (funders audit years later): retain per
your financial-records schedule. Export before decommission; never run
`rollback.js.txt` against real rows.
