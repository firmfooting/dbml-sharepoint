---
title: verify.js.txt
sidebar_position: 4
---

# verify.js.txt

A clock verification, emitted with every build whose pack reads a clock
anywhere: a `today` or `now` save rule, a `today` view window, or a
`[today]` column default. Nearly every pack does. Paste it in the target
site's console *after* `deploy.js.txt`, on the same site, and read the
`[SP-VERIFY] [DONE]` verdict.

## Why it exists

The deploy writes a rule and reads the bytes back, and that is all a
deploy can see. Whether SharePoint then evaluates the rule the way the
mapping meant depends on things no build can observe: which clock a
formula reads, which zone a value is stored in, which path the save came
through. Measured on 2026-09-02, `TODAY()` and `NOW()` inside a validation
formula ran 16 to 20 hours behind the site, and dozens of shipped date
rules had been wrong for months without any gate noticing. The build
now compares date rules with the save instant, and this script is what
checks, on the site itself, that every such cell behaves as measured.

## What it writes

Exactly one list, `_dbml-verify`, created hidden with the tool's own
provenance marker in its Description, and reused on every later run. A
list of that title whose Description is not exactly the marker is
somebody's, and the run stops before touching it. No declared list is
read or written.

The script keeps the list small: one column per clock cell the pack uses,
one item per case, and its own rows from an earlier run recycled first
where the site allows, so both the create and the update paths run each
time. Where recycling is refused, the rows are updated in place and the
report says so. The list itself is never deleted, because a site under a
retention hold cannot delete a list, and the report notes whether the
list read back hidden.

## What it checks

Each check is a **clock cell**, one (sentinel, column kind, target)
combination from `analysis/clock_cells.py`, with the exact rendering the
build emits for it, on a scratch column named for it:

- **Save rules.** A date column under `[D]<=[Modified]` saves yesterday and
  today and refuses tomorrow, on create and on update. An offset rule
  (`today+30` in the pack) saves at thirty days, refuses at thirty-one, and
  saves at twenty-nine. A datetime column under `now` saves an hour ago,
  refuses an hour ahead, and saves an update stamped five seconds before
  its own save. Every save clause is joined into one list rule the way the
  deployer joins them, so the joined shape is exercised too.
- **View windows.** Rows are placed at site-local midnights around today
  and at the pack's own offsets, then queried with the exact `<Value>`
  element a view would carry: `<Today/>`, `<Today OffsetDays="N"/>`, and
  `<Today/>` with `IncludeTimeValue`. The returned rows must be the rows
  the window means.
- **Defaults.** A bare create under a `[today]` default must be returned
  by `Eq <Today/>`, which is how the site itself spells its date. A
  datetime default must land within ten minutes of the row's own
  `Modified`.
- **The formula clock.** A column with the default formula `=TODAY()` is
  filled on a bare create, and the report says how many days behind the
  site's date that clock ran at the hour of the paste. This is
  information, not a failure: the build no longer reads that clock for a
  date rule, and the number is the first thing to look at when a check
  fails.

The one emitted shape that still reads the formula clock, `today+N` on a
datetime column, is recorded the same way: saved or refused, beside the
lag, never judged.

## The verdict

Every finding is `PASS`, `FAIL`, `NOT-ASSESSABLE` or `INFO`, printed with
the cell it belongs to, the value tried and SharePoint's answer. They roll
up to one line:

- `VERIFIED`: every check passed and nothing went unassessed.
- `MISMATCH`: a cell this pack relies on does not behave on this site as
  measured. Read the `FAIL` lines before trusting the deployed rules.
- `NOT-VERIFIED`: something could not be assessed. The site is not shown
  wrong, and not shown right either.

Date cases need the site's own midnight, which the script builds from the
site's reported offset. When the browser it is pasted into matches neither
of the site's two candidate offsets, those cases are `NOT-ASSESSABLE`
rather than guessed; paste from a browser in the site's zone.

A `VERIFIED` run on a live site is also evidence. The cell ids it prints
are the ones the table in `analysis/clock_cells.py` keys on, and a cell
listed there as emitted without an observation can be retired from that
list on the strength of the run.
