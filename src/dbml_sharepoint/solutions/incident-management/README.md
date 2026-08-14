# Incident management

Report it, triage it, fix it, prove it. Two linked lists: `IN_Incident`
(anyone can report) and `IN_CorrectiveAction` (the fixes, each linked to its
incident). Resolution time is calculated automatically.

**The value case.** Incidents reported by email die in inboxes; incidents in
a register get triaged, assigned and closed — and the corrective-action link
is what turns "we fixed it" into "we can show what we changed so it doesn't
recur". The permission model matches the process: **all staff can report**
(a custom report-only permission level — add and read, no editing others'
reports), while the response team maintains records.

**What deploys with it:** seven views — *Open by severity* (the incident
default, grouped and collapsed, with an open **Critical** incident washing
its whole row), *Triage queue*, *Resolved last 90 days*, and on the action
list *Open actions*, *Overdue*, *By owner* (the chase list, grouped by
name) and *By incident* (the closure check: expand an incident, read its
actions) — a severity ladder and a resolution-time bar that takes its
colour from the severity rather than from itself, due dates that go red and
then stop once an action is finished, forms that keep triage and resolution
off the reporter's three-minute New form, save rules on both lists, and
eleven demo rows behind `--seed`.

**Work the folders in order:**

| Step | Folder | You |
| --- | --- | --- |
| 1 | `10-design/` | Fit severity/category language to your incident taxonomy |
| 2 | `20-configure/` | Prefix, review the report-only permission level |
| 3 | `30-deploy/` | Administrator: build, paste, verify both lists + the level |
| 4 | `40-adopt/` | Staff guide: how to report; handlers guide: how to run one |
| 5 | `50-govern/` | Triage SLAs, severity definitions, trend review |

**Customisation points:** `Severity` and `Category` enums — note that
`Critical` drives the row wash and every `Status` member is named in a view
filter, a form rule or a save rule; and whether reporters may also *edit*
their own reports (SharePoint levels can't scope "own items only" — see
`50-govern/governance.md` for the honest options).
