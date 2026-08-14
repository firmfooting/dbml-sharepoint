# Change register — governance

## Ownership

| Role | Held by | Accountable for |
| --- | --- | --- |
| Process owner | *(e.g. ops/IT/quality manager)* | SLAs, the authority table, this document |
| CH Change Managers | The triage group | Queue hygiene, decision chasing, implementation tracking |
| Approvers | Per the authority table | Timely, recorded decisions |

## Impact definitions (edit to your context)

| Impact | Meaning |
| --- | --- |
| High | Affects customers/patients/public, money above your materiality line, regulated obligations, or many teams |
| Medium | Affects more than one team, or changes a controlled document/process |
| Low | Contained within one team, reversible cheaply |

## Decision authority

Edit to your delegations — the register records it, this table
legitimises it.

| Impact | Decided by | SLA (request → decision) |
| --- | --- | --- |
| High | Executive owner of the affected area | 15 business days |
| Medium | Department manager | 10 business days |
| Low | Change manager may approve directly | 5 business days |

`DaysToDecision` makes SLA performance a sortable fact — the process owner
reviews the decision log monthly against these numbers.

## Emergency changes

Emergencies act first, record immediately after: submit within one business
day marked **Emergency**, with what was done and by whose authority. The
monthly review examines every emergency — a pattern of emergencies is a
planning failure wearing a costume.

## Data-quality rules

1. No Under review without an Approver; no Approved/Rejected without
   DecisionDate + DecisionNotes.
2. Approved changes that stall >60 days without implementation come back to
   the monthly review — approve-and-forget is scope creep's front door.
3. Requester text is never edited — managers append, dated.

### What is enforced at save, and what stays a governance check

**Refused at save:**

| Rule | Where it lives |
| --- | --- |
| A decided change (Approved, Rejected, Implemented or Closed) has a DecisionDate | `list_validation` |
| An Implemented change has an ImplementedDate | `list_validation` |
| RequestedDate is not in the future | `column_validation` on `RequestedDate` |
| DecisionDate is not in the future | `column_validation` on `DecisionDate` |

The two list rules share one message, because SharePoint gives a list a
single validation formula and cannot say which branch failed. The two date
rules read only their own column, so they sit there and keep their own
wording — and they earn their place because `DaysToDecision` is computed
from those two dates and nothing else, so a year typed wrong turns an SLA
breach into a nine-month one or a same-day approval into a negative number.

**Still a governance check, and not by choice:**

- **"No Under review without an Approver"** — `Approver` is a person
  column, and SharePoint validation formulas cannot read person columns at
  all. The compensating control is the **Awaiting decision** view: it
  groups by approver, so a request under review with nobody assigned falls
  into a visible empty group rather than disappearing.
- **"No decision without DecisionNotes"** — `DecisionNotes` is a
  multi-line column, which validation formulas also cannot read. The
  decision *date* is enforced; the reasoning is a queue-hygiene check at
  the monthly review.
- **Rule 2, the 60-day stall** — a save rule cannot fire on the passage of
  time; nothing is being saved on the sixty-first day. **Approved, not yet
  implemented** sorts oldest decision first for exactly this, so the
  monthly review reads the top of one view instead of filtering.
- **Rule 3, never editing requester text** — enforced by permissions
  rather than by validation: ordinary Members hold **CH Submit Only**, so
  the person who wrote the Description cannot change it and neither can
  anyone but a change manager.
- **Closed is deliberately absent from the ImplementedDate rule.** A
  rejected change is closed without ever being implemented, so requiring
  the date at Closed would refuse the most ordinary path through the
  register.

## Lifecycle

The decision log is audit evidence: retain per your records schedule,
export before decommissioning, never run `rollback.js.txt` against real rows.
