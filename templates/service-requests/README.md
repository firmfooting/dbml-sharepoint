# Service requests

An internal helpdesk without helpdesk software: one intake list
(`SR_Request`) for facilities, IT, admin and grounds requests — "fix the
meeting-room screen", "new starter needs a chair", "replace the gate code".
Requesters submit and watch progress; service teams work their queues;
days-to-complete is calculated.

**The value case.** Where there's no request system, requests go to
whoever's nicest, twice, by three channels, and the quietest team members
drown silently. One list gives requesters a place that isn't a person,
teams a queue that isn't an inbox, and managers the two facts they never
had: volume and turnaround. This is frequently the highest goodwill-per-
hour deployment in the whole set — staff feel it the first week.

**Work the folders in order:**

| Step | Folder | You |
|---|---|---|
| 1 | `10-design/` | Fit categories/priorities to the teams you actually have |
| 2 | `20-configure/` | Prefix; submit-only requesters, teams contribute |
| 3 | `30-deploy/` | Administrator: build, paste, verify queues |
| 4 | `40-adopt/` | Requesters' one-pager + service teams' queue habit |
| 5 | `50-govern/` | Turnaround targets, triage rules, trend review |

**Customisation points:** the `Category` enum IS your service catalogue —
one value per team that will actually work a queue; don't list services
nobody staffs.
