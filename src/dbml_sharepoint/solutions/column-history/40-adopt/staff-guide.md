# Column history: what it is and who needs it

## Most people never open this list

If you maintain a risk register, an incident log or an action list, this page
is background. You carry on working in your register exactly as before. A
flow watches the columns that matter and records each change here on your
behalf, and there is nothing for you to fill in and no extra step at the end
of your day.

The one thing worth knowing: **your name ends up on these rows**. When you
move a risk from Open to Closed, this list records that you did it, when, and
what the value was before. That is the point of it, and it is the same
information the register's own version history already held, made countable.

## What a row says

One row is one column changing value on one item. Reading left to right:

| Column | Meaning |
| --- | --- |
| Title | The change in one line: `RR_Risk 42 Status: Open -> Closed` |
| Changed (UTC) | When the change happened, in UTC rather than local time |
| Changed By | The person who made the change in the register |
| Source Site Url | Which site the register lives on |
| Source List Title | Which register, by its deployed title |
| Item Id | Which item on that register |
| Item Title | That item's title, so you can read this without opening it |
| Column Name | Which column changed, as it is labelled today |
| Column Internal | Which column changed, as the system knows it |
| Old Value | What it was |
| New Value | What it became |
| Change Key | The reporting join key; ignore it unless you build reports |

## Changed By is not Created By

This list is written by an automation account, so the built-in **Created By**
and **Modified By** on every row say that account's name. They are true and
useless: they record who wrote the log entry, which is always the robot.

**Changed By** is the column that names the actual person. Use that one. If
you are looking at a report and everybody appears to be the same service
account, the report is reading the wrong column.

## The views

- **All changes** is the default: everything, newest first.
- **By site** groups by which site the change happened on, which answers
  "is that team's register actually being maintained".
- **By column** groups by the column's internal name rather than its label,
  so a column's history stays together even after somebody renames it.
- **Recent** is the last week, capped, for a quick look at whether anything
  is arriving at all.
- **My changes** is your own edits across every register in the estate.

## Why UTC

Changed (UTC) is stored in UTC so that changes made in different regions, or
either side of a daylight-saving switch, sort into the true order they
happened in. Your reporting tool converts to local time for display. If you
are reading the list directly and the times look shifted, that is why.

## Old Value is sometimes blank

Two situations produce a blank Old Value, and neither is a fault:

- The first time a column is observed, there is no previous value to record.
- Some triggers report only what a value **is**, not what it **was**.

The full history is still intact. The value before a change is the New Value
on the previous row for the same item and the same column, which is how
reports reconstruct it.

## What to do if a row looks wrong

Do not edit it. You will not have permission to, and that is deliberate: a
hand-edited row is a false history that no report can tell from a true one.

A wrong row means a flow is wired wrong, and the fix belongs in the flow.
Tell whoever administers the central logging site, and tell them which
register and which column, because a mis-wired flow is usually producing
wrong rows for every item on that register rather than just the one you
noticed.

If the underlying fact is wrong, correct it in **the register**. The flow
observes that correction and records it here as another change, which is the
honest record: the value was wrong, then somebody fixed it.
