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

## Odometer integrity

1. Readings come from the odometer at the time — the calculated TripKm
   makes gaps and overlaps visible in the *Per vehicle* view (this trip's
   OdoStart should equal the last trip's OdoEnd; a mismatch means an
   unlogged trip or a misread).
2. **Monthly** (fleet owner): skim each vehicle's continuity — chase gaps
   while memory exists; negative TripKm rows get fixed by their driver.
3. Fuel receipts/odometer at service give independent anchor points;
   note them.

## Fleet review (the bonus the paper book never gave you)

**Quarterly**: *Monthly km by vehicle* — utilisation per vehicle. The car
doing 40 km a month is a lease payment looking for a justification;
the one doing 4,000 needs its service interval watched (pair with
equipment-maintenance for the service schedule itself).

## Data-quality rules

1. No trip without Purpose, OdoStart and Driver; OdoEnd within a day of
   return.
2. Late entries are marked late; odometer continuity is reviewed, not
   assumed.
3. Damage or warning-light Notes get acted on (service request or
   workshop) — the log is also the fleet's early-warning channel.

## Lifecycle

Retain trip logs per your tax/records requirements (Australia: five years
for substantiation, typically). Export by financial year for finance.
Never run `rollback.js` against real rows.
