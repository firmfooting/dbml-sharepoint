# Onboarding tracker

Every new starter, and every task that has to happen across HR, IT,
facilities, finance and their manager before and after day one. Two lists:
`OB_Starter` and `OB_OnboardingTask` (one row per task per starter, tagged
by function).

**The value case.** Onboarding is the textbook multifactorial process: four
departments, one deadline, and no single owner of the whole. When it's run
by email, the new starter arrives to no laptop, no access, no desk — and
everyone is sure someone else dropped it. This tracker gives each function
its own group in the open-task queue, every individual a *My tasks* view
that follows the signed-in user, the manager a per-starter checklist, and
HR a single *anything overdue before a start date* view. Value lands with
the very first starter.

**Deploys with:** seven views (starters in progress, starting soon, and
complete-or-withdrawn; tasks grouped by function, grouped by starter, the
current user's own queue, and the overdue-before-start list), sectioned
forms on both lists, a Done Date that only appears once a task is Done,
overdue colouring, three save rules, and ten demo rows.

**Work the folders in order:**

| Step | Folder | You |
| --- | --- | --- |
| 1 | `10-design/` | Fit functions/status language to your org |
| 2 | `20-configure/` | Prefix; everyone-contributes security (it's cross-team) |
| 3 | `30-deploy/` | Administrator: build, paste, verify; agree the standard task set |
| 4 | `40-adopt/` | Coordinator + per-function guides |
| 5 | `50-govern/` | The standard task list, leavers variant, privacy notes |

**Customisation points:** the `TaskFunction` enum; your standard task set
(documented in `50-govern/governance.md` — the template deliberately ships
the checklist as governance, not seed data, so you review it before use).
