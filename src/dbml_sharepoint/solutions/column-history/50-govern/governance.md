# Column history: governance

## What this list is for, and what it is not

It is an **event log**. One row records that one column on one item took a new
value at a point in time. It is written by automation, read by reporting, and
edited by nobody.

It is not a register, not a workflow surface and not a system of record. The
registers out in the estate remain the record; this list holds the shape of
how they changed. If the two ever disagree, the register is right and a flow
is wrong.

## Change Key: the reporting join, pinned

`ChangeKey` exists to relate a history row to the register row it describes,
inside a Power BI model, with no bridge table. It works because it is
**byte-identical** to the row key the deployer's own reporting pack builds for
that register.

### The expression

The authority is `_row_key_m` in
`src/dbml_sharepoint/generators/reportgen.py`, which the source comment calls
"THE ONE definition of the key format". For the risk register it emits this M
expression, and every other list differs from it only in the quoted title:

```text
SiteRoot & "|" & "RR_Risk" & "|" & Number.ToText([Id])
```

So a flow must compose, as plain text:

```text
<SiteRoot>|<ListTitle>|<ItemId>
```

A pipe between each part. No spaces around the pipes, no trailing separator.
For item 42 of the risk register on a quality site:

```text
https://contoso.sharepoint.com/sites/quality|RR_Risk|42
```

### The three parts, exactly

**`SiteRoot`** is not the raw site URL. The reporting query normalises it from
the `SiteUrl = "..."` literal at the top of that register's
`reporting/powerquery/<ListTitle>.pq`, and a flow must produce the same
normalised string or the relationship matches nothing:

- Trailing slashes removed.
- Cut at the first `/_api/`, `/_layouts/`, `/lists/` or `/sitepages/` segment,
  so a list, form, page or API URL is reduced back to the site root. A correct
  site URL is left untouched.
- Case is **preserved** as the operator typed it in Power BI. The M
  comparison is exact text, so a flow writing a differently-cased host or path
  produces a key that will not join even though both URLs address the same
  site. Agree one spelling of each site URL and use it in every flow.

A root site collection is legitimately `https://tenant.sharepoint.com` with no
`/sites/` segment, so there is nothing here to validate against.

**`ListTitle`** is the **deployed** list title, which carries the family
prefix. The reporting pack builds it as `prefix + table.name`
(`reportgen.py`, where each entity's plan is constructed), so the risk
register's `Risk` table is `RR_Risk` and that is what belongs in the key.
Writing the unprefixed DBML table name is the most likely way to get this
wrong.

It is the title rather than the list GUID, deliberately and not as an
oversight. The reporting query addresses the list by title in
`getbytitle('<title>')` regardless, so a rename breaks the query outright
either way; the title therefore adds no failure mode the query does not
already have, and it costs no extra round trip.

**`ItemId`** is the item's `Id`, rendered as text with no padding and no
thousands separator, which is what `Number.ToText` produces.

### The key is universal, not per list

The same format covers every list on every site, because it carries the site
and the list inside it. That was a deliberate correction in the deployer:
the key was once site plus id, and since every SharePoint list numbers its
items from 1, two lists on one site produced colliding keys the moment their
queries were appended, which is exactly the multi-site multi-list model the
reporting guide tells operators to build. Wrong row counts, wrong
relationships, nothing raising an error.

So one `ChangeKey` column joins to **every** register's `<Entity> Key` column.
In Power BI, `ChangeKey` is the many side against each register's key on the
one side.

### Nothing enforces this at save time

The rule "Change Key equals Source Site Url, Source List Title and Item Id
joined by pipes" is not something this deployer can declare. Its condition
grammar is a field, an operator and a value (`src/dbml_sharepoint/model/
conditions.py`), and the value is a literal or a dated sentinel. There is no
way to write another column there, so no declaration can say that three
columns concatenate into a fourth.

That is a limit of the declaration, not of SharePoint. The save rule this
list does declare renders as `=OR(ISBLANK([Changed (UTC)]),[Changed
(UTC)]<=[Modified])`, because the `now` sentinel resolves to `[Modified]`, so
the formulas this tool emits already compare one column against another.
Whether SharePoint would accept the `CONCATENATE` form has not been probed,
and nothing here should be read as saying it would not.

It is therefore a **governance check**, listed below, and the reason the three
components are stored as their own columns as well as inside the key. A
reviewer can recompute the key from the row and compare.

## Durations are computed, not stored

There are deliberately **no** `EffectiveTo` or `IsCurrent` columns, and this
list is deliberately not a slowly-changing dimension.

Every row is an event: a change happened at `ChangedUtc`. A duration is the
gap to the **next** event for the same `ChangeKey` **and** the same
`ColumnInternal`:

```text
duration = next(ChangedUtc) - ChangedUtc
           partitioned by (ChangeKey, ColumnInternal)
           ordered by ChangedUtc
```

The current state is the last event in each partition, and its duration runs
to now rather than to a next row.

**Why not store it.** An `EffectiveTo` column has to be written twice: once
when the row is created with an unknown end, and again when the next change
arrives and closes it. That second write is a read-modify-write from a flow
against a growing list, it has no transaction around it, and every failure
mode it has produces silently wrong data rather than an error. A row whose
close never happened reads as "still in this state", which is
indistinguishable from the truth. Computing the gap at query time cannot
develop that inconsistency, because there is only ever one write per event.

Note that this is a different pattern from the type-2 change log the deployer
maintains for its own schema changes. Do not copy the SCD-2 shape from there
into here.

`ColumnInternal` rather than `ColumnName` in the partition, because a column
renamed in SharePoint keeps its internal name. Partitioning on the display
name splits one column's history in two on the day somebody retitles it, and
the durations either side of the rename come out wrong with no error.

## The flow contract

The full specification is in `30-deploy/deploy.md`. The governance summary:

- **Trigger:** "When an item is created or modified" on the watched register,
  followed by a watched-column condition that exits the flow when nothing of
  interest changed.
- **`ChangedBy` must be the trigger item's `Editor`**, not the flow identity.
  The flow runs as a service account, so the row's own Created By and
  Modified By name that account and answer nothing. A row whose Changed By
  equals its Created By is that account naming itself, unless the service
  account genuinely made the edit out on the register.
- **`ChangedUtc` must be the trigger item's `Modified` stamp**, not the flow
  run time.
- **`OldValue`** is the trigger's before-value where the trigger supplies one,
  and blank otherwise. It is not a required column for exactly this reason.
- **Values are string-coerced by the flow**, with one fixed spelling per type.
- **Write target:** `getbytitle('dbml_ColumnHistory')` on the central logging
  site.
- **The flow's service account needs Contribute on this list**, granted by
  membership of `dbml History Writers`.
- Flows bind columns by **internal name**. A column renamed in SharePoint
  keeps its internal name and the flow keeps working; a column renamed *in
  the DBML* is a new column and breaks it.
- The deployer's `watched_lists` coordination applies where a watched register
  is itself declared as a watched list.

## Keep a register of flows

Nothing in this list records which flows write to it, and there is no way to
work it out from the data, because every row arrives from the same service
account. Without a register, a flow that stops firing is invisible: the rows
simply stop, and no view distinguishes "nothing changed on that register" from
"the flow has been broken since March".

Maintain a list of, for each flow: the site and register it watches, the
columns it watches, its owner, and the date it was last confirmed working.
Review it on the same cadence as the checks below.

## Governance checks

These are the things the platform cannot enforce, so somebody has to.

| Check | Cadence | What to look at |
| --- | --- | --- |
| `ChangedBy` is a person, and not the flow | Monthly | Two failures, one cause. A **blank** Changed By is a flow that never mapped the trigger item's Editor. A Changed By **equal to the row's own Created By** is a flow that mapped its own identity instead, which fills *My changes* for the service account and empties it for everybody else. Created By reaches Power BI because `reporting.system_columns` is on, so the comparison is one step there. Group *All changes* by Source List Title to find which flow |
| `ChangeKey` is well formed | Quarterly | Recompute `<SiteRoot>\|<ListTitle>\|<ItemId>` from the row's own three columns and compare. A mismatch silently drops the row out of every report that joins |
| `ListTitle` carries its prefix | Quarterly | A key built from the unprefixed table name joins to nothing |
| Site URL spelling is consistent | Quarterly | Group *By site*. Two groups differing only in case or a trailing slash means two flows disagree, and one of them is producing unjoinable keys |
| Flows are still firing | Monthly | Against the flow register above. A register with no rows this month is either quiet or broken |
| No hand-written rows | Quarterly | Contribute is limited to `dbml History Writers`. Confirm the group's membership is still only service accounts |
| Growth against retention | Annually | See below |

## Retention and growth

This list has no natural ceiling. It grows with the rate of change across
every register you watch, forever, and it is the one list in this library
where an unindexed filter would silently truncate a view rather than merely
run slowly. Every filtered and grouped view here keys on an indexed column
for that reason, and a new view must do the same.

Decide a retention position and write it down:

- **Keep everything.** Simplest, and defensible while the estate is small.
  Revisit when the list passes the list view threshold in a way the indexes
  stop covering.
- **Trim by age.** Delete rows older than N years. Cheap, and it costs you the
  early history of long-lived items.
- **Trim by item.** Delete history for items that have been closed longer than
  N years. Better aligned to why anyone reads this, and more work to run.

Whatever you choose, note that **deleting history changes past reports**. A
duration computed as the gap between events gets longer when the earlier event
is deleted, because the gap is now measured from whatever remains. Trim on a
boundary your reports do not cross, and record the cut-off date where report
authors will see it.

## Privacy

Every row names a person and says what they did and when. Taken together the
list is a per-person activity trail across the whole estate, which is a
materially different thing from any single register and should be assessed as
such under your privacy obligations. It is more revealing than the registers
it draws from, because it spans all of them.

Site Members hold Read. If that is too broad for your organisation, narrow it
here rather than in the flows: the flows need Contribute regardless, and
reducing what they write to would break the reporting rather than protect
anybody.

## Changing the schema

A column removed or renamed in the DBML is a **flow change**, not just a
schema change. Flows bind by internal name, so a renamed column means every
flow writing to it fails at the write step, and it fails per run rather than
loudly and once.

Before any schema change: check the flow register, plan the flow edits
alongside the redeploy, and bump `schema_version` in
`20-configure/release.yaml`. Sealed columns block the accidental version of
this through the UI, which is why `seal_columns` is on.
