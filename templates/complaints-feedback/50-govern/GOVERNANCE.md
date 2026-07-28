# Complaints & feedback — governance

## Ownership

| Role | Held by | Accountable for |
|---|---|---|
| Process owner | *(e.g. quality/consumer-experience manager)* | SLAs, trend reporting, privacy, this document |
| Handlers | CF Feedback Handlers | Acknowledgement, investigation, response, learning |
| Recorders | CF Feedback Recorders | Faithful capture at the point of receipt |

## Sector note — healthcare (and other regulated sectors)

Check your statutory complaints scheme before adopting this register as
the system of record: some sectors mandate a platform or prescribe
categories and timeframes (health-complaints commissioners, aged-care
schemes). Where mandated, use this register only for what the mandate
does not cover, and record referrals as the escalation section describes.
No patient-identifiable clinical detail enters this list — complaint
substance at process level, clinical content in clinical systems. See
[templates/HEALTHCARE.md](../../HEALTHCARE.md).

## Severity definitions & response SLAs (put statutory timeframes here)

| Severity | Meaning | Acknowledge within | Close within |
|---|---|---|---|
| Critical | Alleged serious harm, systemic failure, media/regulator interest | 1 business day | per your scheme |
| Serious | Significant individual impact or repeated issue | 2 business days | 20 business days |
| Standard | Everything else | 5 business days | 30 business days |

The calculated day-counts make SLA performance sortable facts, and both
draw as bars **coloured by Severity** so a number reads against the right
target without anyone consulting this table. The bars' scales are set from
the row above — 10 days for acknowledgement, 30 for closure. **If you
change these timeframes, change the two `max:` values in
`20-configure/mapping.yaml` in the same edit**, or the bars will look
reassuring about a breach.

## What is enforced at save, and what stays a governance check

| Enforced at save | Rule |
|---|---|
| `Received Date`, `Acknowledged Date`, `Closed Date` | None may be in the future |
| The list | Anything past **Received** must have an Acknowledged Date |
| The list | A **Closed** item must have an Outcome and a Closed Date |

The two list rules share a single message, because SharePoint gives a list
exactly one validation formula. Each names the field it wants, and the
form shows that field at the moment the rule can fire — a rejection naming
something the handler cannot see is what the conditional visibility rules
exist to prevent.

Three things this register cares about are **not** enforceable, and it is
worth recording why so nobody spends an afternoon on it:

- **`Learning` at closure.** It is a rich-text column, and SharePoint
  validation formulas cannot reference rich text at all — not for a null
  test, not for anything. Making it enforceable would mean giving up the
  formatting that lets a handler write a paragraph. The monthly review is
  what catches an empty one.
- **The acknowledgement timeframe.** `Days To Acknowledge` is a calculated
  column, and validation formulas cannot read calculated columns either.
  The platform can insist there *is* an acknowledgement date; only a
  person can judge that four days on a Critical item was too slow.
- **Faithful capture.** That Detail says what the person said, rather than
  what the recorder wishes they had said, is a training matter. Recorders
  cannot edit after saving, which is the structural half of it.

## Escalation

- Critical items: process owner notified same day; executive briefed.
- Anything alleging staff misconduct leaves this register for the HR
  process — record "Referred externally" with a pointer, not the detail.
- Complainants who remain dissatisfied: record the referral to your
  external body (ombudsman/commissioner) in the row.

## Privacy (load-bearing)

1. Site membership = recorders + handlers + owners only; **ordinary
   members have no access by design** — widening it is a governance
   decision recorded here.
2. Detail carries the substance, initials/roles for third parties, and no
   health/financial identifiers beyond what the item needs.
3. Subject-access: complainants may request their records; the process
   owner handles with your privacy officer.
4. Retention per your scheme's rules; this register is usually the system
   of record — treat exports accordingly.

## The learning loop (the actual point)

- **Monthly**: process owner reviews **Closed last 30 days** — outcomes,
  day-counts against SLA — and **The learning shelf**, which is every
  closed item with its `Learning` in the row. Recurring themes become
  change requests or risk entries (pair naturally with the
  change-register and risk-register templates).
- **Quarterly**: trend report to the executive: volumes, SLAs, themes,
  changes made. Feedback nobody learns from is administration, not quality.

### Two limits on the numbers you quote

Both are properties of the platform rather than choices, and both matter
the moment a figure leaves this list for a board pack:

- **"Closed last 30 days" is a rolling window, not a calendar month.**
  CAML has no calendar-month predicate. On the first business day of a
  month the rolling and calendar answers differ noticeably.
- **Both response clocks are averaged on the screen.** The view groups by
  feedback type, collapsed, and shows a mean Days To Acknowledge and a
  mean Days To Close under each type as well as overall. That is the
  committee figure; it needs no export.
  A **median** does need one — SharePoint aggregates mean, count, sum, min
  and max, and a median is not among them. If your board reads medians
  because a single very old complaint distorts a mean, take that from the
  generated reporting bundle and say so in the pack.

## Lifecycle

Never run `rollback.js` against real rows; export before decommission,
then dispose per retention rules.
