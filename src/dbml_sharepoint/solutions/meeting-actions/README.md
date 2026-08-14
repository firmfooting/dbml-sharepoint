# Meeting actions

Meetings, the decisions they made, and the actions they produced, linked.
Three lists: `MA_Meeting`, `MA_Decision`, `MA_ActionItem` (both linked to
their meeting).

**The value case.** The fastest-payback template here: every team already
has meetings, and almost none can answer "what did we decide in March, and
did anyone do the actions?" Deploy before your next meeting; by the one
after that, the *Open by person* view replaces the ritual of re-reading old
minutes. Decisions become findable facts instead of folklore.

**Deploys with:** nine views (recent meetings and meetings by forum; the
decision log and decisions by meeting; and (on actions) open by person,
the current user's own list, overdue, actions by meeting, and the
done-and-dropped history), sectioned forms on all three lists, overdue
colouring, a Completed Date that only appears once an action is Done, two
save rules, and thirteen demo rows. Paste it seeded and the first agenda
item works before you have held a meeting.

**Work the folders in order:**

| Step | Folder | You |
| --- | --- | --- |
| 1 | `10-design/` | Adjust meeting types to your forums |
| 2 | `20-configure/` | Prefix; default everyone-can-record security |
| 3 | `30-deploy/` | Administrator: build, paste, verify links |
| 4 | `40-adopt/` | Chairs/minute-takers guide: the 5-minute habit |
| 5 | `50-govern/` | Action follow-up discipline, decision hygiene |

**Customisation points:** `MeetingType` enum; whether Decisions are used at
all (small teams often start with Meetings + Actions and add Decisions when
they feel the need; deploying the list costs nothing).
