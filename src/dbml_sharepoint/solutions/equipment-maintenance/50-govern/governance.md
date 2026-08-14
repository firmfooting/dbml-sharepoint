# Equipment maintenance — governance

## Ownership

| Role | Held by | Accountable for |
| --- | --- | --- |
| Maintenance owner | *(e.g. facilities/biomed manager)* | The schedule, frequencies, escalation, this document |
| EM Maintenance Team | The working group | Record-then-reschedule discipline, evidence |
| All staff | — | Not using out-of-service items; reporting faults |

## Frequency defaults by class (edit to your obligations)

| Class | Default interval | Source of the rule |
| --- | --- | --- |
| Biomedical / clinical | Per manufacturer + your biomed programme (typically 12 months) | AS/manufacturer/biomed policy |
| Electrical test-and-tag | Per environment class (e.g. 12 months clinical, 5 years fixed office) | AS/NZS 3760 as applied by your policy |
| Fire and emergency | Per your fire-services contract schedule | AS 1851 as applied |
| Vehicles | Per service schedule | Manufacturer / fleet policy |

Each item stores its actual `FrequencyMonths`; these defaults are the
starting rule, and deviations are deliberate (note why on the item). The
list refuses an interval below one month — an interval of zero is a
schedule that never advances.

## Overdue escalation

- The **Overdue** view's target state is *empty*. Anything appearing there
  is worked or explained within 5 business days.
- It filters `Status = In service`, which means *still in use and out of
  test*. That is the clinical and legal exposure, and it is why the view
  is narrower than "everything past its date". Items already withdrawn are
  overdue too and live in **Out of service**, which is reviewed daily.
- Overdue **clinical/biomedical or fire** items: maintenance owner
  escalates to the responsible executive at 5 business days; the item is
  risk-assessed for continued use (pair with the risk-register template)
  or removed from service — silence is not an option that exists.
- Chronic overdue patterns are a capacity conversation with the data to
  prove it (**Due 60 days** is your forward workload).

## What is enforced at save, and what stays a governance check

| Enforced at save | Rule |
| --- | --- |
| `Equipment Tag` | Unique across the register (a schema constraint) |
| `Frequency Months` | At least 1 |
| `Event Date` | Cannot be in the future |
| `MaintenanceEvent` list | Anything other than a clean **Passed** needs a Note |

**Data-quality rule 1 below is deliberately NOT a save rule, and this is
the most important sentence in this document.** "Every in-service item has
a future-or-today Next Due Date" is correct as a standard and wrong as a
formula: enforced at save, it would refuse to *store* an overdue item —
the exact state the Overdue view exists to surface, and the one a real
register must be able to hold. A rule that makes a problem unrecordable
does not fix the problem, it hides it. The overdue date turns red, the row
appears in Overdue, and a person acts. That is the design.

Two further governance checks, for the same kind of reason:

- **Evidence on every event.** A URL column is a compound value and
  SharePoint validation formulas cannot read one. Making it mandatory
  would mean a `not null` in the schema, which then refuses to record any
  historical event whose paperwork predates the register — so the evidence
  standard below is enforced by review, at the point where it is actually
  read.
- **Record-then-reschedule.** Nothing in the platform can do step 2 for
  you: an event cannot read its equipment's frequency, so there is no
  calculated next-due date and no automation. This is the discipline the
  whole register rests on, and it is a habit.

## Evidence standard

An event without linked evidence is hearsay: internal work links the
completed checklist/report; contractor work links their report or
certificate, filed in your records system (the register indexes, the
records system holds). Accreditation and insurance reviews read the
**Service history** view — grouped by item, newest first — and that is the
audience to write for.

## Data-quality rules

1. Every In-service item has a future-or-today NextDueDate; the reschedule
   step is part of recording, not optional. **Deliberately not enforceable
   — see above.**
2. Failed events and Out-of-service status always travel together. Not
   enforceable either: they live on two different lists, and a save rule
   reaches only its own. The **Failures** view is the reconciliation.
3. Tags are never reused; retired history is never deleted.
4. Anything that passed with actions has those actions in Notes with an
   owner, and they are chased from the **Actions arising** view. **The
   Note is enforced at save; that it names an owner is not.**

## Lifecycle

Maintenance history retention follows your safety/records schedule (long —
it outlives the equipment). Export before decommission; never run
`rollback.js.txt` against real rows.
