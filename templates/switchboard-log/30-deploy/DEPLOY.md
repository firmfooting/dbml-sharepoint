# Deploying the switchboard log (administrator)

Shared procedure: [`templates/README.md`](../../README.md) with
`<name> = switchboard-log`. Template-specific notes below.

## Before you build

- [ ] `SB_` prefix free on the target site.
- [ ] The `CodeType` enum matches your emergency procedures exactly
      (ships with AS 4083 — edit for your jurisdiction/local codes
      **before** first deploy).
- [ ] **Privacy check**: site membership = switchboard operators,
      supervisors and owners only (ordinary members get no grant by
      design).
- [ ] The paper books being replaced have a cutover date — parallel
      running splits the record.

## After the paste — verification checklist

- [ ] All four lists exist: `SB_CodeEvent`, `SB_MessageLog`, `SB_Key`,
      `SB_KeyMovement` (Key before KeyMovement).
- [ ] Duration spot-check: code Announced `03:20`, All-clear `03:47` →
      **DurationMinutes = 27**. Message Taken `02:00`, Relayed `02:12` →
      **MinutesToRelay = 12**.
- [ ] `Key.KeyRef` rejects a duplicate; a KeyMovement's Key lookup offers
      the catalogue.
- [ ] As an ordinary site Member: **no lists visible**.
- [ ] **Load the key catalogue** — every key at the switch, with its tag
      ref and restrictions, before go-live. Any key currently out gets an
      open KeyMovement.
- [ ] Populate **SB Switchboard Operators**; delete the test rows.
- [ ] Bookmark the three "New item" forms on the switchboard terminal —
      speed at 3 a.m. is adoption.
- [ ] Even as an owner: changing a deployed column's type, choices or
      settings is refused (sealed) and List settings offers no "Delete
      this list"; a display-name rename is still possible — it is
      drift, reverted and reported at the next re-paste.

## Recommended views

| List | View | Filter / sort |
|---|---|---|
| CodeEvent | Code log | Newest first — the emergency-planning record |
| CodeEvent | Real events only | IsDrill = No |
| MessageLog | Pending relay | Status = Pending relay, Urgency then oldest — the live board |
| MessageLog | Overnight report | TakenAt = last 24h — the morning handover |
| KeyMovement | Keys out now | Status = Out — the glance that answers "who has it?" |

## Redeploying

Bump `schema_version`, rebuild, re-paste.
