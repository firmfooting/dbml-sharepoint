# Vehicle log — governance

## Ownership

| Role | Held by | Accountable for |
|---|---|---|
| Fleet owner | *(e.g. corporate services/finance manager)* | The use policy, substantiation quality, fleet review, this document |
| Every driver | — | Their trips, honestly and promptly |
| Workshop / maintenance | — | Acting on Notes; pairing with equipment-maintenance for services |

## The use policy (decide, record, enforce)

- [ ] Private use permitted? ______ (if never: remove the enum values)
- [ ] Commute use permitted, for whom? ______
- [ ] Who may drive: employees only / volunteers with approval / ______

Substantiation note (Australia): a compliant FBT log book needs the
business/private split over a representative period with purposes
recorded — this register captures exactly that, *if* Purpose lines are
specific and TripType is honest. Confirm the format with your tax adviser;
the register is the evidence, they own the method.

Both non-business trip types render amber in every view. That is
deliberate: they are the rows an adviser and an auditor look at first, and
making them visually rare is a mild but real pressure toward honesty.

## What is enforced at save, and what stays a governance check

| Enforced at save | Rule |
|---|---|
| `Rego` | Unique across the fleet (a schema constraint) |
| `Departed At` | Cannot be in the future |
| `Odometer Start`, `Odometer End` | Neither may be negative |
| The list | A trip with a Returned At must have an Odometer End |

**The rule everyone expects and cannot have: that the closing odometer
exceeds the opening one.** SharePoint validation formulas compare a column
to a literal, and the condition grammar this template is written in
expresses only that — column-to-column comparison is not available. The
compensating control is loudness rather than prevention: `Trip km` goes
negative, and in the **By vehicle** view the entire row washes dusty rose.
It is the one row-level signal this template declares, and it is on that
view because that is where odometer continuity is read.

Everything else is a governance check:

- **Purpose specificity.** "Errands" saves. Only a person can tell it
  apart from "Warragul clinic - equipment delivery", and the whole tax
  value of the log rests on the difference.
- **Trip type honesty.** Nothing stops a private trip being logged as
  business.
- **Timeliness.** A trip logged three weeks late saves exactly like one
  logged at the key cupboard. The marked-late rule below is what covers
  it.

## Odometer integrity

1. Readings come from the odometer at the time. The calculated Trip km
   makes gaps and overlaps visible in the **By vehicle** view — this
   trip's Odometer Start should equal the last trip's Odometer End, and a
   mismatch means an unlogged trip or a misread.
2. **Monthly** (fleet owner): skim each vehicle's continuity in **By
   vehicle** — chase gaps while memory exists; pink rows get fixed by
   their driver.
3. Fuel receipts and the odometer at service give independent anchor
   points; note them.

## Fleet review (the bonus the paper book never gave you)

**Quarterly**: **Last 30 days by vehicle**, or a wider export —
utilisation per vehicle. The car doing 40 km a month is a lease payment
looking for a justification; the one doing 4,000 needs its service
interval watched (pair with equipment-maintenance for the schedule
itself).

### Two limits on the numbers you quote

Both are properties of the platform, not choices, and both matter the
moment a figure leaves this list for a fleet paper or an FBT return:

- **The view is a rolling thirty days, not a calendar month.** CAML has no
  calendar-month predicate. For a financial-year or calendar-month
  figure, export.
- **The per-vehicle total is on the screen.** *Last 30 days by vehicle*
  groups by vehicle, collapsed, and totals `TripKm`, so SharePoint shows
  a kilometre figure under each vehicle and one for the whole window. Run
  the quarterly fleet review from the view.
  What still needs an export is a **calendar** period — a financial year,
  or a true calendar month — because the window is a rolling thirty days.

## Data-quality rules

1. No trip without Purpose, Odometer Start and Driver; Odometer End within
   a day of return. **The last part is enforced at save once Returned At
   is filled in.**
2. Late entries are marked late; odometer continuity is reviewed, not
   assumed.
3. Damage or warning-light Notes get acted on (service request or
   workshop) — the log is also the fleet's early-warning channel.

## Lifecycle

Retain trip logs per your tax/records requirements (Australia: five years
for substantiation, typically). Export by financial year for finance.
A disposed vehicle stays in `VE_Vehicle` — it drops out of *The fleet*
view but keeps its trip history readable. Never run `rollback.js` against
real rows.
