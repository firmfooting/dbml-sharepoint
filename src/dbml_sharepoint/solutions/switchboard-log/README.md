# Switchboard log

*Theme: operations & service — built for hospital/facility switchboards
and after-hours operations desks.*

The switchboard's three paper books, digitised: the **emergency code log**
(`SB_CodeEvent` — announcements, locations, all-clears, drills, with
duration calculated), the **message book** (`SB_MessageLog` — after-hours
calls taken and relayed, with time-to-relay calculated), and the **key
register** (`SB_Key` catalogue + `SB_KeyMovement` — who has which key
right now).

**The value case.** Switchboard is the organisation's after-hours nervous
system, and its records are the evidence nobody can reconstruct later: the
emergency planning committee needs every code activation with times and
all-clears (drills included); the 2 a.m. message that never reached the
on-call manager needs a trail; and "who has the pharmacy key?" needs an
answer that isn't a shrug. Paper books answer none of this searchably —
and the code log especially is asked for by name in emergency-preparedness
reviews.

**Privacy posture:** switchboard traffic includes sensitive content
(welfare calls, police contact) — ordinary site members get **no access**;
operators record, supervisors oversee.

**What deploys with it:** twelve views across the four lists. The two that
change the job most are **Still running** — every code with no all-clear,
with that cell reading "Running" in red rather than sitting empty, which
is the gap governance calls the classic one — and **Pending relay**, the
live board, where an **Emergency** message still waiting washes its whole
row. Also **Drills** grouped by code type, so the coverage *gap* is
visible and not just the coverage; **By key**, every movement grouped under
its key for the quarterly audit; and **Relay times** against the published
escalation targets. Plus two-pass forms that ask for the all-clear, the
relay and the return only once they exist, save rules that refuse a
relayed message with nobody named, and nineteen demo rows behind `--seed`.

**Work the folders in order:**

| Step | Folder | You |
| --- | --- | --- |
| 1 | `10-design/` | Fit the code set and urgency language to your procedures |
| 2 | `20-configure/` | Prefix; operators-only model |
| 3 | `30-deploy/` | Administrator: build, paste; load the key catalogue |
| 4 | `40-adopt/` | The operator habits: log codes live, relay-then-record |
| 5 | `50-govern/` | Code-log review, message follow-up, key audits |

**Customisation points:** the `CodeType` enum ships with the Australian
AS 4083 code set — replace with your jurisdiction's, and note that it is
the grouping column of the drill-coverage view, so the code set you deploy
is the report you get; `Urgency` and the two `Status` enums are named in
view filters, form rules and save rules, so read the "Before you build"
block in `30-deploy/deploy.md` before editing any of them.
