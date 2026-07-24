# Equipment maintenance — governance

## Ownership

| Role | Held by | Accountable for |
|---|---|---|
| Maintenance owner | *(e.g. facilities/biomed manager)* | The schedule, frequencies, escalation, this document |
| EM Maintenance Team | The working group | Record-then-reschedule discipline, evidence |
| All staff | — | Not using out-of-service items; reporting faults |

## Frequency defaults by class (edit to your obligations)

| Class | Default interval | Source of the rule |
|---|---|---|
| Biomedical / clinical | Per manufacturer + your biomed programme (typically 12 months) | AS/manufacturer/biomed policy |
| Electrical test-and-tag | Per environment class (e.g. 12 months clinical, 5 years fixed office) | AS/NZS 3760 as applied by your policy |
| Fire and emergency | Per your fire-services contract schedule | AS 1851 as applied |
| Vehicles | Per service schedule | Manufacturer / fleet policy |

Each item stores its actual `FrequencyMonths`; these defaults are the
starting rule, and deviations are deliberate (note why on the item).

## Overdue escalation

- The **Overdue** view's target state is *empty*. Anything appearing there
  is worked or explained within 5 business days.
- Overdue **clinical/biomedical or fire** items: maintenance owner
  escalates to the responsible executive at 5 business days; the item is
  risk-assessed for continued use (pair with the risk-register template)
  or removed from service — silence is not an option that exists.
- Chronic overdue patterns are a capacity conversation with the data to
  prove it (the Due-60-days view is your forward workload).

## Evidence standard

An event without linked evidence is hearsay: internal work links the
completed checklist/report; contractor work links their report or
certificate, filed in your records system (the register indexes, the
records system holds). Accreditation and insurance reviews read the
*Per item* view — that's the audience to write for.

## Data-quality rules

1. Every In-service item has a future-or-today NextDueDate; the reschedule
   step is part of recording, not optional.
2. Failed events and Out-of-service status always travel together.
3. Tags are never reused; retired history is never deleted.

## Lifecycle

Maintenance history retention follows your safety/records schedule (long —
it outlives the equipment). Export before decommission; never run
`rollback.js` against real rows.
