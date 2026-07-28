# Equipment maintenance — guide

## For all staff (read access)

Before using equipment you're unsure about: open **EM_Equipment** — it
opens on **The schedule**, every item that isn't retired, soonest due
first — find the tag, and check **Status** and **Next Due Date**. A due
date that has passed shows red. Out of service means out of service; the
register is the authority, not the sticker's optimism.

Spot something broken? Tell the maintenance team (or raise it via the
service-requests template if you run one) — don't just put it back in the
cupboard for the next person.

## For the maintenance team

### The one two-step habit: record, then reschedule

Every time work is done on an item — by you or a contractor:

1. **Record the event**: `EM_MaintenanceEvent` → New — what, when, who,
   **Result**, and the **Evidence URL** (service report / test certificate
   filed in the records system first, then linked).
2. **Reschedule the item**: open the equipment row and set **Next Due
   Date** = event date + the item's `Frequency Months`.

Step 2 is the schedule. An event recorded without the reschedule silently
removes the item from future work — which is why the habit is one motion,
never two people. **Nothing in the platform can do it for you**: an event
cannot read its equipment's frequency, so there is no calculated column
here and no automation. The register makes the gap visible; you close it.

### Results discipline

- **Passed with actions**: the list will not let you save without a
  **Note**, and the actions go there with an owner. They then appear in
  the **Actions arising** view, which is where they get chased — an action
  noted nowhere else is an action lost.
- **Failed - removed from service**: same rule, same reason. Then set the
  equipment row's Status to **Out of service - awaiting maintenance** in
  the same minute (that is the whole value — there is no plain "Out of
  service"), and physically tag the item.
  Register first, sticker second — people trust the sticker; auditors
  trust the register; keep them agreeing.
- Back in service only after a passing event: record it, restore Status,
  reschedule.

### The views you work from

- **Overdue** — still in use and out of test. This is the one that matters
  and its target is **empty**. It filters on `Status = In service`
  deliberately: an item already withdrawn is overdue too, and it is in
  **Out of service**, where you are already looking.
- **Due 60 days** — the forward work plan, including anything already
  late.
- **Service history** — every event, grouped under its item. This is what
  an accreditor or an insurer reads; expand the item, read the record.
- **Failures** and **Actions arising** — the two results that leave
  something undone.

### Contractors

Contractor visits get recorded by whoever receives the report — same day,
`PerformedBy` = the contractor, evidence linked. "The contractor has it in
their system" is not your register; your obligations don't outsource.

### New and retiring equipment

New maintained item → register it with frequency and first Next Due Date
before first use. Retired → Status **Retired**; history stays (it's the
evidence trail), tag never reused. Retiring an item is also what stops its
due date shouting: the overdue colouring is guarded on Retired and on
nothing else.
