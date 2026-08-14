# Service requests

An internal helpdesk without helpdesk software: one intake list
(`SR_Request`) for facilities, IT, admin and grounds requests — "fix the
meeting-room screen", "new starter needs a chair", "replace the gate code".
Requesters submit and watch progress in *My requests*; service teams work
their queues; days-to-complete is calculated and drawn as a bar coloured
by the request's priority.

**The value case.** Where there's no request system, requests go to
whoever's nicest, twice, by three channels, and the quietest team members
drown silently. One list gives requesters a place that isn't a person,
teams a queue that isn't an inbox, and managers the two facts they never
had: volume and turnaround. This is frequently the highest goodwill-per-
hour deployment in the whole set — staff feel it the first week.

**What deploys with it:** six views — *Open by category* (the default,
grouped and collapsed), *Facilities queue*, *IT queue*, *Waiting*, *My
requests* (which uses SharePoint's own current-user filter, so it is one
view for everybody) and *Turnaround* — a five-section form that hides
assignment and completion from the requester until they mean something,
a save rule that refuses a completion with no date or no resolution, and
six demo requests behind `--seed`.

**Work the folders in order:**

| Step | Folder | You |
| --- | --- | --- |
| 1 | `10-design/` | Fit categories/priorities to the teams you actually have |
| 2 | `20-configure/` | Prefix; submit-only requesters, teams contribute |
| 3 | `30-deploy/` | Administrator: build, paste, verify queues |
| 4 | `40-adopt/` | Requesters' one-pager + service teams' queue habit |
| 5 | `50-govern/` | Turnaround targets, triage rules, trend review |

**Customisation points:** the `Category` enum IS your service catalogue —
one value per team that will actually work a queue; don't list services
nobody staffs. Two of its members are named inside deployed view filters
and one enum's *alphabetical order* sets queue precedence — read the
"Before you build" block in `30-deploy/deploy.md` before editing either.
