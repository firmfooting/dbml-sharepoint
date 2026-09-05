# Column history

*Theme: governance, risk & compliance.*

One list (`dbml_ColumnHistory`), deployed once to your central logging site,
that Power Automate flows write into. Every time a watched column changes on
any register anywhere in the estate, a flow posts one row here saying which
item changed, which column, from what to what, when, and who did it. Power BI
then builds status history, durations and trend reporting over registers that
individually only ever store the current value.

**The value case.** A SharePoint list holds the present tense. A risk that
sat at Extreme for five months and was closed yesterday looks identical to one
raised and closed the same afternoon, and no view can tell you which. Version
history knows, but it is per item, unqueryable in bulk and invisible to
reporting. This list turns each change into a row you can count, so "how long
does an incident sit in triage", "how many risks moved up a band this quarter"
and "which registers are actually being maintained" become answerable.

**What deploys with it:** five views (*All changes*, *By site*, *By column*,
*Recent*, *My changes*), a four-section form, an index on every column a view
filters or groups on, a save rule that refuses a change timestamped in the
future, and five demo rows behind `--seed` so the views have something in
them before your first flow runs.

**This family is different from every other one in the library**, in three
ways worth knowing before you start:

- **It deploys once, not once per site.** Every register in the estate writes
  to this single list. It belongs on the central logging site alongside the
  deployment log.
- **The deployer never writes to it.** Nothing in `deploy.js.txt` puts rows
  here. Power Automate does, and you build those flows yourself; the contract
  they must satisfy is specified in `30-deploy/deploy.md`.
- **The prefix is part of the contract.** `dbml_` plus `ColumnHistory` is what
  makes the list `dbml_ColumnHistory`: one word, no spaces, so a flow binds
  `getbytitle('dbml_ColumnHistory')` and a URL without escaping. Changing
  `prefix:` renames the list and breaks every flow already bound to it.

**Work the folders in order:**

| Step | Folder | You |
| --- | --- | --- |
| 1 | `10-design/` | Decide which columns on which registers are worth watching |
| 2 | `20-configure/` | Confirm the prefix; nominate the flow service account |
| 3 | `30-deploy/` | Administrator: build, paste; then build the flows to the contract |
| 4 | `40-adopt/` | Who reads this and who never needs to |
| 5 | `50-govern/` | The Change Key expression, retention, and the flow register |

**Customisation points:** which registers and which columns you watch (start
with one lifecycle column on one register, not the whole estate); whether you
keep history for closed items forever or trim it on a retention schedule; and
whether `ItemTitle` is worth carrying, which it is as soon as anyone reads
this list directly rather than through Power BI.

**The one thing this list gets wrong when it is wired up wrong:** `ChangedBy`.
The flow runs as a service account, so the row's own Created By and Modified
By are that account and answer nothing. The flow has to copy the *trigger
item's* Editor into `ChangedBy` explicitly. Skip that and every row is
attributed to a robot, which is the one question the list existed to answer.
The *My changes* view is empty for everybody when this is wrong.
