# Deploying the column history (administrator)

Shared procedure: [`templates/README.md`](../../README.md) with
`<name> = column-history`. Run order: **assess** the target site (paste
`build/assess.js.txt`, read-only; the verdict must be COMPATIBLE or an accepted
DEGRADED) -> **review** `build/deploy-manifest.md` (must show 0 validation
errors) -> **paste** `build/deploy.js.txt` from a Site Owner's console ->
**verify** against the checklist below. Template-specific notes follow.

Deploy this to your **central logging site**, once for the whole estate, not
once per register site. Every flow in every site writes to this one list.

## Before you build

- [ ] The central logging site exists and you are a Site Owner on it.
- [ ] `dbml_` prefix free on that site. Note that unlike other families the
      prefix here is not a free choice: see below.
- [ ] The flow service account is decided and licensed for Power Automate.
- [ ] You have picked the **first** register and the **first** column to
      watch. One column on one register, proven end to end, then widen. A
      flow fanned out across a whole estate on day one produces a list nobody
      trusts and cannot debug.

### The prefix is not a free choice here

Every other family in this library invites you to rewrite `prefix:`. This one
does not. The list title is `<prefix><EntityName>`, so `dbml_` plus
`ColumnHistory` is exactly what produces `dbml_ColumnHistory`, and flows bind
to that title:

```text
_api/web/lists/getbytitle('dbml_ColumnHistory')/items
```

One word, no spaces, so nothing has to be URL-escaped and nothing breaks when
a flow designer round-trips the string. Change the prefix and you rename the
list, and every flow already bound to it starts failing at the write step.

## Optional: the seeded demonstration build

An empty column history demonstrates nothing, and its whole point is the
shape of the data rather than any one row. To see the views and the grouping
working before a single flow exists, rebuild with `--seed`:

```bash
dbml-sharepoint build \
  --schema 10-design/schema.dbml \
  --mapping 20-configure/mapping.yaml \
  --release 20-configure/release.yaml \
  --site-url https://yourtenant.sharepoint.com/sites/your-site \
  --site-role default \
  --seed \
  --out ./build
```

That bundle contains an extra file, `demo-data.js.txt`. Paste `deploy.js.txt`
first, then `demo-data.js.txt`, from the same bundle. It creates five changes
across two sites and three registers, including one row with no Old Value
(the first-observation case) and one with no Changed By (what a flow that has
not been wired to the trigger item's Editor produces). Delete them with
`rollback.js.txt`, which confirms per list before deleting.

## After the deploy: permissions

The deploy creates `dbml History Writers` and grants it Contribute. It is
empty. **Add the flow's service account to it by hand.** Nothing in the
deploy can do this for you, because nothing in the deploy knows which
identity your flows will run as.

Site Members and Site Owners get **Read**, not Contribute, deliberately. A
hand-typed row here is a false history that reporting cannot distinguish from
a real one, and the way to correct the record is to correct the register and
let the flow observe it.

---

## The flow contract

This is the part you build. The deployer provisions the list and stops; every
row comes from a flow you author. A flow satisfies this contract when all of
the following hold.

### Trigger

**When an item is created or modified** on the register list you are
watching. The column-change trigger available in some connectors is also
acceptable and gives you a cleaner before-value; see *Old Value* below.

Add a **watched-column condition** immediately after the trigger, so the flow
exits without writing when the modification did not touch a column you care
about. Without it every save on the register writes a row saying nothing
changed, and the list fills with noise faster than anything reads it.

The deployer's own `watched_lists` coordination applies: if the register you
are watching is itself declared as a watched list elsewhere, keep the two
declarations consistent so a redeploy does not surprise a running flow.

### Field mappings

Flows bind SharePoint columns by **internal name**, and the internal names
here are stable across display renames. Write these:

| Column (internal) | What the flow writes |
| --- | --- |
| `Title` | A composed one-liner: `RR_Risk 42 Status: Open -> Closed` |
| `ChangedUtc` | The **trigger item's** `Modified` timestamp, in UTC |
| `ChangedBy` | The **trigger item's** `Editor`, `triggerOutputs()?['body/Editor']` |
| `SiteUrl` | Absolute URL of the register's site, no trailing slash |
| `ListTitle` | The register's deployed list title, prefix included: `RR_Risk` |
| `ItemId` | The trigger item's `ID` |
| `ItemTitle` | The trigger item's `Title` |
| `ColumnName` | The column's display name |
| `ColumnInternal` | The column's internal name |
| `OldValue` | The before-value, coerced to a string; blank if unavailable |
| `NewValue` | The after-value, coerced to a string |
| `ChangeKey` | `<SiteUrl>\|<ListTitle>\|<ItemId>`, exactly. See below |

### ChangedBy is the one that gets this wrong

**The flow runs as a service account.** The row it creates therefore has that
service account as its own Created By and Modified By, and those two columns
answer nothing at all about who changed the register. They record who wrote
the log entry, which is always the robot.

So `ChangedBy` has to be populated explicitly, from the trigger item:

```text
triggerOutputs()?['body/Editor']
```

Set the SharePoint "Create item" action's *Changed By Claims* field to that
expression's `Claims` property, or map the editor's email into the person
column, depending on which connector shape you are using.

**How to tell you got it wrong:** open the *My changes* view as somebody who
has definitely edited a watched register. If it is empty while rows keep
arriving in *All changes*, `ChangedBy` is not being mapped and every row in
the list is anonymous. Fix it before you widen the flow to more registers,
because rows already written cannot be repaired from anything the row itself
holds.

### ChangedUtc is the trigger item's timestamp, not the flow's

Write the trigger item's `Modified` value, not `utcNow()`. A flow queued
behind a retry, a throttle or a nightly recurrence writes minutes or hours
after the change happened, and every duration computed from this column
inherits that delay silently. The save rule on this column refuses a
timestamp in the future, which catches the coarsest version of this mistake
at the moment the flow author makes it, but it cannot catch a stamp that is
merely late.

### Old Value, and why it is not required

`OldValue` is the one column here that is optional, and that is deliberate.
The "when an item is modified" trigger reports the item's current state and
does not carry what the value was a moment ago. Depending on your connector
and trigger you will get the before-value, or you will not.

- If your trigger supplies it, write it.
- If it does not, leave `OldValue` blank rather than inventing a value.
- To recover it properly, keep the previous row for the same `ChangeKey` and
  `ColumnInternal` and read its `NewValue`. That is the same computation
  Power BI does for durations, and `50-govern/governance.md` writes it out.

A blank `OldValue` is also the honest representation of the first observation
of a column, where there genuinely is no previous value. Making the column
required would have forced flows to write a placeholder that reporting could
not distinguish from a real empty string, and would have failed the flow run
outright on every trigger that supplies nothing.

### Coerce both values to strings

`OldValue` and `NewValue` are multi-line text. A choice, a number, a date, a
person and a lookup all have to arrive as strings, and the flow decides how.
Pick one spelling per type and keep it, because Power BI groups on these
values verbatim:

- Dates as ISO 8601 (`2026-09-05`), not a locale format that changes with the
  flow's regional settings.
- People as display name, or as email, but not sometimes one and sometimes
  the other.
- Empty as an empty string, not the word `null`.
- Multi-value columns as a delimited list with a fixed separator and a fixed
  order, or they will read as changed every time SharePoint returns them in a
  different order.

### Change Key, which has to match byte for byte

`ChangeKey` is what lets Power BI relate a history row to the register row it
describes, with no bridge table, and it only works because it is identical to
the row key the deployer's own reporting pack builds for that register:

```text
<SiteRoot>|<ListTitle>|<ItemId>
```

Three parts, pipe separated, no spaces around the pipes. Two of them are
easy to get subtly wrong:

- `SiteRoot` is the site URL with any trailing slash removed and cut back
  from a list, form or API URL to the site itself. Compared as exact text, so
  agree one spelling per site and use it in every flow.
- `ListTitle` is the register's **deployed** title with its prefix, `RR_Risk`
  rather than `Risk`. The unprefixed name joins to nothing.

A wrong key is silent: the row saves, the views show it, and it drops out of
every report that joins. `50-govern/governance.md` writes the derivation out
in full, including where in the deployer that format is defined.

### The write target

```text
POST <central-site>/_api/web/lists/getbytitle('dbml_ColumnHistory')/items
```

The flow's service account needs **Contribute** on this list, which it gets
by being a member of `dbml History Writers` (see above). It does not need any
permission on the central site beyond that.

---

## Verify

- [ ] The list `dbml_ColumnHistory` exists on the central logging site.
- [ ] `dbml History Writers` exists, holds Contribute, and contains the flow
      service account.
- [ ] Site Members hold Read and not Contribute.
- [ ] All five views are present: *All changes*, *By site*, *By column*,
      *Recent*, *My changes*.
- [ ] The form header shows `Change: <title>` on a saved row and `New column
      change` before a title is typed.
- [ ] Make one real change on the watched register. Within the flow's latency
      a row appears in *Recent*.
- [ ] That row's **Changed By** is you, not the service account. This is the
      check that matters most.
- [ ] That row's **Change Key** reads `<site>|<list>|<id>` with no spaces
      around the separators.
- [ ] Saving a row by hand with a Changed (UTC) in the future is refused with
      the message about the trigger item's Modified timestamp.
