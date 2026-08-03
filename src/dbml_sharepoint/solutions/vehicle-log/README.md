# Vehicle log

*Theme: operations & service*

The pool-car paper log book, digitised: `VE_Vehicle` (the fleet catalogue)
and `VE_Trip` (every trip: driver, odometer out/in with **kilometres
calculated**, and the business purpose that makes the record
tax-defensible).

**The value case.** Paper log books get wet, run out of lines, live in the
glovebox of the one car that's out, and — the expensive part — go missing
exactly when finance needs them: in Australia, the business-use log book
is **FBT evidence**, and elsewhere it's mileage/expense substantiation.
Digitised, every trip is attributed and timestamped, kilometres compute
themselves from the odometer readings, and per-vehicle usage falls out as
a view (which is also your fleet right-sizing data — the car that does
40 km a month is a lease you don't need).

**What deploys with it:** six views — *Out now* (the Trip default, the
glance that answers "who has the car?"), *By vehicle* (the continuous log
book, grouped and collapsed), *My trips* (SharePoint's own current-user
filter, so it is one view for every driver), *Last 30 days by vehicle*,
and the fleet catalogue's two — a two-halves form that asks for the return
readings only once there are any, a save rule that refuses a returned trip
with no closing odometer, and a row wash that turns a negative-kilometre
trip pink in the view where odometer continuity is read. Four demo
vehicles and six demo trips with continuous odometer readings ship behind
`--seed`.

**It totals the kilometres.** *Last 30 days by vehicle* groups by vehicle
and sums `TripKm`, so the per-vehicle figure a fleet review wants is on
the screen rather than in an export. The window is a rolling thirty days
rather than a calendar month — CAML has no calendar predicate — so a
financial-year or true calendar-month figure still needs an export, and
`50-govern/governance.md` says so where the review is described.

**Work the folders in order:**

| Step | Folder | You |
|---|---|---|
| 1 | `10-design/` | Fit purpose/vocabulary to your fleet rules |
| 2 | `20-configure/` | Prefix; every-driver-records model |
| 3 | `30-deploy/` | Administrator: build, paste; load the fleet |
| 4 | `40-adopt/` | The out-and-back habit (30 seconds each end) |
| 5 | `50-govern/` | FBT/substantiation rules, odometer integrity, fleet review |

**Customisation points:** whether private use is permitted and how it's
recorded (governance carries the decision — the schema supports both; both
non-business trip types render amber deliberately).
