# Equipment maintenance — guide

## For all staff (read access)

Before using equipment you're unsure about: open **EM_Equipment**, find the
tag, check **Status** and **NextDueDate**. Out of service means out of
service — the register is the authority, not the sticker's optimism.
Spot something broken? Tell the maintenance team (or raise it via the
service-requests template if you run one) — don't just put it back in the
cupboard for the next person.

## For the maintenance team

### The one two-step habit: record, then reschedule

Every time work is done on an item — by you or a contractor:

1. **Record the event**: `EM_MaintenanceEvent` → New — what, when, who,
   **Result**, and the **evidence link** (service report / test
   certificate filed in the records system first, then linked).
2. **Reschedule the item**: open the equipment row and set **NextDueDate**
   = event date + the item's `FrequencyMonths`.

Step 2 is the schedule. An event recorded without the reschedule silently
removes the item from future work — which is why the habit is one motion,
never two people.

### Results discipline

- **Passed with actions**: the actions go in the event Notes *and* get an
  owner — an action noted nowhere else is an action lost.
- **Failed - removed from service**: set the equipment row's Status to
  **Out of service** in the same minute, and physically tag the item.
  Register first, sticker second — people trust the sticker; auditors
  trust the register; keep them agreeing.
- Back in service only after a passing event: record it, restore Status,
  reschedule.

### Contractors

Contractor visits get recorded by whoever receives the report — same day,
`PerformedBy` = the contractor, evidence linked. "The contractor has it in
their system" is not your register; your obligations don't outsource.

### New and retiring equipment

New maintained item → register it with frequency and first NextDueDate
before first use. Retired → Status **Retired**; history stays (it's the
evidence trail), tag never reused.
