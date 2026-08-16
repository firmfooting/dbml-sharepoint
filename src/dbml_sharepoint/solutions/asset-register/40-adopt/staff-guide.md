# Asset register: staff guide

*For anyone who issues, receives, moves or retires equipment.*

## The one rule

**If equipment moves, the register moves.** Issued a laptop? Update
**Assigned To**. Sent a monitor to storage? Update **Status** and
**Location**. The register is only as good as its last update.

## Adding an asset (when new kit arrives)

1. **AS_Asset** -> **New**.
2. **What it is**: **Title**: what it is, plainly. **Asset tag**: the
   sticker/serial physically on the item. The register refuses
   duplicates. **Category**, and anything the next holder should know in
   **Notes**.
3. **Where it is**: **Location** (pick from the list; if a location is
   missing, add it to **AS_Location** first, or ask an owner to), and
   **Status**.
4. **Purchase and warranty**: date, cost and warranty expiry from the
   invoice while you still have it. Warranty length calculates itself and
   draws as a bar. The list will refuse a warranty expiry with no purchase
   date, because the term cannot be worked out from one of them.

## Issuing / returning

- Issue: set **Assigned To** to the person, Status **Assigned**.
- Return: clear **Assigned To**, set Status **In service** or **In
  storage**, correct the **Location**.
- Repair: Status **Under repair**, note the fault in **Notes**.

## Retiring / disposal

Set Status **Retired** (kept, out of use) or **Disposed** (gone). **Never
delete the row**. Disposal evidence is exactly what audits ask for. Put
the disposal method and date in Notes.

Clear **Assigned To** *before* you change the status. Once the item is
Retired or Disposed the field disappears from the form, and it keeps
whatever was in it, so an item disposed while still assigned stays
assigned to someone forever.

## The views

- **Stocktake** (opens by default): everything currently in service or
  assigned, in Location then Asset Tag order. That is the order you walk
  the building in, which is what makes it a stocktake sheet rather than a
  list.
- **By holder**: grouped by person, assigned items only.
- **By location**: grouped by place, everything still in the fleet.
- **Warranty expiring**: anything falling due in the next sixty days,
  soonest first. A warranty already lapsed shows red.
- **Retired and disposed**: the history, out of the way of the working
  views.

## Leavers

Before someone's last day: open **By holder** and expand their group.
Everything assigned to them gets returned and re-registered. That group is
the checklist, and it should be empty before their account is disabled.
