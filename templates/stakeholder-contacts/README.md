# Stakeholder contacts

A shared organisational memory of who you deal with and what was said.
Three lists in a chain: `SC_Organisation` → `SC_Contact` →
`SC_Interaction` (every meeting, call or email note linked to its contact).

**The value case.** When the relationship lives in one person's inbox, it
leaves when they do. This register is CRM-shaped without CRM weight:
partnerships, government relations, media, suppliers, community groups —
any team that manages external relationships gets a shared view of *who
owns which relationship* and *when we last spoke*, on day one. It's also
the classic "we should have written that down" fix: the interaction log
turns handovers from an hour of oral history into a filter.

**Deploys with:** six views (organisations by owner and by type; contacts
active-by-organisation and moved-on; interactions recent and grouped per
contact for handover), sectioned forms on all three lists whose headers
carry the privacy rule to the moment someone is typing, an active/moved-on
chip, one save rule, and thirteen demo rows that name roles rather than
inventing people — because this register's privacy posture is load-bearing
and the seed is the first thing anyone sees.

**Work the folders in order:**

| Step | Folder | You |
|---|---|---|
| 1 | `10-design/` | Fit organisation/interaction types to your world |
| 2 | `20-configure/` | Prefix; everyone-contributes model |
| 3 | `30-deploy/` | Administrator: build, paste, verify the lookup chain |
| 4 | `40-adopt/` | The write-it-down habit, in three minutes |
| 5 | `50-govern/` | Relationship ownership, privacy, contact hygiene |

**Customisation points:** `OrgType` and `InteractionType` enums; privacy
posture (this register holds personal data — the governance doc's privacy
rules are load-bearing, not boilerplate).
