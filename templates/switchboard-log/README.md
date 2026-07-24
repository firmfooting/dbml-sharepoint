# Switchboard log

*Theme: operations & service — built for hospital/facility switchboards
and after-hours operations desks*

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

**Work the folders in order:**

| Step | Folder | You |
|---|---|---|
| 1 | `10-design/` | Fit the code set and urgency language to your procedures |
| 2 | `20-configure/` | Prefix; operators-only model |
| 3 | `30-deploy/` | Administrator: build, paste; load the key catalogue |
| 4 | `40-adopt/` | The operator habits: log codes live, relay-then-record |
| 5 | `50-govern/` | Code-log review, message follow-up, key audits |

**Customisation points:** the `CodeType` enum ships with the Australian
AS 4083 code set — replace with your jurisdiction's; `Urgency` and key
vocabulary to your procedures.
