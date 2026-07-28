# Service requests — governance

## Ownership

| Role | Held by | Accountable for |
|---|---|---|
| Service owner | *(e.g. facilities/ops manager)* | Turnaround targets, the category catalogue, this document |
| Queue lead (per category) | A named person per team | Their queue's hygiene and turnaround |
| SR Service Teams | The working group | Working the queues honestly |

## Turnaround targets (edit to your reality — then publish them)

| Priority | Accepted within | Completed within |
|---|---|---|
| Urgent | Same business day | 2 business days (or Waiting with reason) |
| Normal | 2 business days | 10 business days |
| Low | 5 business days | 20 business days |

Targets are promises to staff — set ones you can keep. The **Turnaround**
view is where you find out whether you did, with one caveat worth knowing
before you build a report on it: it shows a **rolling ninety days** and
**no totals**. See "What the report can and cannot tell you" below.

## What is enforced at save, and what stays a governance check

| Enforced at save | Rule |
|---|---|
| `Requested Date` | Cannot be in the future |
| `Completed Date` | Cannot be in the future |
| The list | A request set to **Completed** or **Declined** must have both a Completed Date and a Resolution |

That last one is data-quality rule 1 below, and until this template's
uplift nothing enforced it — a completed request with no date has no
turnaround, and it is invisible in the only view that measures the team.
The refusal names all of it in one message, because SharePoint gives a
list exactly one validation formula and one message.

Everything else here is a **governance check** — a habit or a review, not
something the platform refuses:

- **Declines say where to go instead.** `Resolution` is required at
  decline; that it names a next step is a judgement, and only a person can
  make it.
- **Detail and photos.** `Detail` is a rich-text column, and SharePoint
  validation formulas cannot reference rich text at all. A one-word
  request saves.
- **Priority honesty.** Nothing stops a requester marking everything
  urgent. Queue leads re-set it, which is the triage rule below.
- **Category accuracy.** A mis-categorised request lands in the wrong
  queue and stays there until someone moves it; the grouped default view
  is what makes a stray one visible.

## Triage rules

- Queue leads may re-set Priority (with a word in Resolution) — requesters
  propose, teams dispose.
- Wrong category: re-categorise, don't bounce — the request moves queues
  invisibly to the requester.
- Anything that's really a **change** (new spend, new capability, policy)
  gets Declined with a pointer to the change-register — the two templates
  are designed to hand off to each other.

## Monitoring

- **Weekly** (queue leads): the **Waiting** view — everything waiting has
  a reason and a next step in `Resolution`; nothing hides there.
- **Monthly** (service owner): the **Turnaround** view, grouped by
  category — volumes, day-counts against targets, decline rate. Chronic
  misses are a resourcing conversation with data, not a blame conversation
  with vibes.

### What the report can and cannot tell you

Two limits, both deliberate, both stated here so a monthly pack is not
built on a misunderstanding:

- **It is a rolling ninety days, not a calendar month.** CAML — the filter
  language SharePoint views are written in — has no calendar-month or
  calendar-quarter predicate; `today-90` is what exists. On the first
  business day of a month the two answers differ noticeably.
- **There are no totals.** The view groups by category and shows each
  request's own day-count and a bar, but there is no sum, mean or count
  row under a group. Column aggregations are not a capability this tool
  ships. For a monthly mean, export the view and total it in Excel, or use
  the generated reporting bundle.

## Data-quality rules

1. No Completed without Completed Date + Resolution. **Enforced at save.**
2. Declines always say why and where to go instead.
3. Requests are never deleted — Declined and Completed are the terminal
   states; the history is the demand data.

## Lifecycle

Turnaround history is your demand evidence for budget bids — keep at least
two years. Export before decommission; never run `rollback.js` against
real rows.
