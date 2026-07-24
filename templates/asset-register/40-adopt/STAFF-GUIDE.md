# Asset register — staff guide

*For anyone who issues, receives, moves or retires equipment.*

## The one rule

**If equipment moves, the register moves.** Issued a laptop? Update
`AssignedTo`. Sent a monitor to storage? Update `Status` and `Location`.
The register is only as good as its last update.

## Adding an asset (when new kit arrives)

1. **AS_Asset** → **New**.
2. **Title**: what it is, plainly. **Asset tag**: the sticker/serial you
   physically track — the register refuses duplicates.
3. **Category**, **Location** (pick from the list — if a location is
   missing, add it to **AS_Location** first or ask an owner to).
4. **Purchase date / cost / warranty expiry** from the invoice while you
   still have it. Warranty length calculates itself.

## Issuing / returning

- Issue: set **AssignedTo** to the person, Status **Assigned**.
- Return: clear **AssignedTo**, set Status **In service** or **In storage**,
  correct the **Location**.
- Repair: Status **Under repair**, note the fault in **Notes**.

## Retiring / disposal

Set Status **Retired** (kept, out of use) or **Disposed** (gone). **Never
delete the row** — disposal evidence is exactly what audits ask for. Put the
disposal method/date in Notes.

## Leavers

Before someone's last day: filter *By holder* on their name; everything
assigned to them gets returned and re-registered. That view is the
checklist.
