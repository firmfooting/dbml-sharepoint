# Change register — governance

## Ownership

| Role | Held by | Accountable for |
|---|---|---|
| Process owner | *(e.g. ops/IT/quality manager)* | SLAs, the authority table, this document |
| CH Change Managers | The triage group | Queue hygiene, decision chasing, implementation tracking |
| Approvers | Per the authority table | Timely, recorded decisions |

## Impact definitions (edit to your context)

| Impact | Meaning |
|---|---|
| High | Affects customers/patients/public, money above your materiality line, regulated obligations, or many teams |
| Medium | Affects more than one team, or changes a controlled document/process |
| Low | Contained within one team, reversible cheaply |

## Decision authority (edit to your delegations — the register records it, this table legitimises it)

| Impact | Decided by | SLA (request → decision) |
|---|---|---|
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

## Lifecycle

The decision log is audit evidence: retain per your records schedule,
export before decommissioning, never run `rollback.js` against real rows.
