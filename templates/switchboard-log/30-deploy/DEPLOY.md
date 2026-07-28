# Deploying the switchboard log (administrator)

Shared procedure: [`templates/README.md`](../../README.md) with
`<name> = switchboard-log`. Run order: **assess** the target site (paste
`build/assess.js`, read-only; the verdict must be COMPATIBLE or an accepted
DEGRADED) → **review** `build/deploy-manifest.md` (must show 0 validation
errors) → **paste** `build/deploy.js` from a Site Owner's console →
**verify** against the checklist below. Template-specific notes follow.

## Before you build

- [ ] `SB_` prefix free on the target site.
- [ ] The `CodeType` enum matches your emergency procedures exactly
      (ships with AS 4083 — edit for your jurisdiction/local codes
      **before** first deploy). It is the grouping column of the **Drills**
      view, so the code set you deploy is the coverage report you get.
- [ ] **`Urgency` and both `Status` enums are named in view filters, form
      rules, a formatter map and the save rules.** `Emergency` drives the
      row wash on the live message board; `Pending relay` and `Relayed`
      decide what the message form shows and what it refuses; `Out` and
      `Returned` do the same on the key register. Renaming a member
      changes behaviour, not just wording. Decide **before first deploy**.
- [ ] **Privacy check**: site membership = switchboard operators,
      supervisors and owners only (ordinary members get no grant by
      design).
- [ ] The paper books being replaced have a cutover date — parallel
      running splits the record.

## Optional: the seeded demonstration build

Twelve views over four empty lists demonstrate nothing, and the two
signals that matter most — a code with no all-clear, and an Emergency
message nobody has relayed — cannot be shown at all without data. Rebuild
with `--seed`:

```bash
dbml-sharepoint build \
  --schema templates/switchboard-log/10-design/schema.dbml \
  --mapping templates/switchboard-log/20-configure/mapping.yaml \
  --release templates/switchboard-log/20-configure/release.yaml \
  --site-url https://yourtenant.sharepoint.com/sites/your-site \
  --site-role default \
  --seed \
  --out ./build
```

That bundle contains an extra file, `demo-data.js`. Paste `deploy.js`
first, then `demo-data.js`, from the same bundle. It creates five code
events (three real, two drills, one still running), five messages covering
every urgency and every status, four keys including one lost, and five key
movements. Nothing in it contains clinical detail — operators log what
switchboard *did*, and the healthcare note in `50-govern/GOVERNANCE.md` is
emphatic about that boundary.

**Delete the demo rows before active use.** Every demo Title begins with
`[DEMO] `, so they are obvious in every view, they are matched by Title on
re-paste (running it twice never duplicates), and `rollback.js` treats a
list whose rows are *all* demo-marked as demo-only content. Do not seed a
site that already holds real switchboard records.

## After the paste — verification checklist

- [ ] All four lists exist: `SB_CodeEvent`, `SB_MessageLog`, `SB_Key`,
      `SB_KeyMovement` (Key before KeyMovement).
- [ ] All twelve declared views appear, and if you seeded, none is empty:
      - `SB_CodeEvent`: **Code log** (default), **Real events only**,
        **Drills**, **Still running**;
      - `SB_MessageLog`: **Pending relay** (default), **Last 24 hours**,
        **Relay times**;
      - `SB_Key`: **The key register** (default), **Retired and lost
        keys**;
      - `SB_KeyMovement`: **Keys out now** (default), **Out since before
        today**, **By key**.
      The generated **All Items** recovery view is hidden from the modern
      view bar on all four lists.
- [ ] **What could not be built as the old recommended-views table wrote
      it**, three rows' worth:
      - **"Pending relay — Urgency then oldest"**. SharePoint sorts a
        Choice column as text, and this enum sorts *Emergency, Routine,
        Urgent* — so neither sort direction gives the intended order, and
        there is no numeric rank column to sort on. The view sorts oldest
        first; urgency is carried by the pill and by the **row wash**,
        which turns an Emergency row dusty rose. Confirm the wash before
        you rely on the board.
      - **"Overnight report — TakenAt = last 24h"**. CAML has no
        rolling-hours predicate. **Last 24 hours** filters `TakenAt ≥
        today-1`, which is midnight yesterday — so it shows the last one
        to two days depending on when it is opened. That is right for a
        morning handover and wrong for an exact 24-hour count.
      - **A per-key movement history**. There is no per-parent view in
        SharePoint. **By key** groups every movement under its key,
        collapsed — one view rather than one per key, and it stays correct
        as keys are added. It is the quarterly audit's working surface.
      - Four views were added beyond the table: **Still running**,
        **Drills** (grouped by code type, because governance asks for
        drill coverage and a flat list cannot show a *gap* — a code type
        with no group is a code type nobody has drilled), **Relay times**
        and **Out since before today**.
- [ ] Duration spot-check: code Announced `03:20`, All-clear `03:47` →
      **Duration Minutes = 27**. Message Taken `02:00`, Relayed `02:12` →
      **Minutes To Relay = 12**, drawn as a bar coloured from that
      message's **Urgency** rather than from the number.
- [ ] **A code with no All Clear At renders the word "Running" in red,
      with a warning icon, in that column, in every view.** That is the
      single most important cell in the whole template: governance calls
      the missing all-clear "the classic gap", and an empty cell says
      nothing while a red "Running" says it is either live now or was
      never closed off.
- [ ] `Key.KeyRef` rejects a duplicate; a KeyMovement's Key lookup offers
      the catalogue.
- [ ] The forms are two-pass, matching the operators' guide. On a **new
      code event**, *All Clear At* and *Event Notes* are absent — during a
      code the job is the code, and it is two fields and save. On a **new
      message**, *Relayed To* and *Relayed At* are absent, and appear on
      the Edit form only once Status is **Relayed**. On a **new key
      movement**, *Returned At* is absent and appears once Status is
      **Returned**.
- [ ] Save rules. Every datetime column refuses a future value with its
      own message — and note the shape: each compares against midnight
      *tomorrow*, because SharePoint's `TODAY()` is midnight and a rule
      written against today would refuse everything logged after 00:00,
      which at a switchboard is everything. The message list refuses
      **Relayed** with no *Relayed To* or no *Relayed At*; the key
      movement list refuses **Returned** with no *Returned At*.
- [ ] Two things this register wants that are **not** enforced at save,
      and `50-govern/GOVERNANCE.md` says what carries them instead:
      - **Code-event completeness** (times, all-clear, notes). `Event
        Notes` is rich text, which SharePoint validation formulas cannot
        reference at all; and requiring an All Clear At would refuse to
        save the row at the moment a code is *announced*, which is exactly
        when it must be recorded. **Still running** is the control.
      - **Contemporaneous entry.** A record typed at 07:10 about a 03:20
        event saves exactly like one typed at 03:20. The honest-gap note
        in the row, and item version history, are what carry it.
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

## Redeploying

Bump `schema_version`, rebuild, re-paste.
