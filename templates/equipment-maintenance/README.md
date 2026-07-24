# Equipment maintenance

*Theme: operations & service — built for safety-critical maintenance
(biomedical equipment, test-and-tag, fire safety, plant)*

What must be tested or serviced, how often, when it's next due, and the
evidence it happened. Two lists: `EM_Equipment` (each maintained item with
its frequency and **next-due date**) and `EM_MaintenanceEvent` (every
service, test or calibration, linked, with result and evidence).

**The value case.** The asset-register knows what you own; this register
knows whether it's *safe to use*. In a health service the stakes are
explicit — an out-of-test infusion pump is a clinical risk and an audit
finding — but the pattern is universal: test-and-tag, fire equipment,
vehicles, plant. The *Overdue* view replaces the ring-binder and the
contractor's memory, and every event carries its evidence link, which is
precisely what accreditors and insurers ask to see.

**Work the folders in order:**

| Step | Folder | You |
|---|---|---|
| 1 | `10-design/` | Fit equipment types and result language to your context |
| 2 | `20-configure/` | Prefix; maintenance-team-maintains model |
| 3 | `30-deploy/` | Administrator: build, paste, verify; load the schedule |
| 4 | `40-adopt/` | The record-then-reschedule habit; out-of-service discipline |
| 5 | `50-govern/` | Frequencies by class, overdue escalation, contractor evidence |

**Customisation points:** `EquipmentType` enum; frequency defaults per
class live in governance (the schema stores each item's actual frequency).
