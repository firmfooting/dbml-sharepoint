# Change register

One intake for change requests — IT systems, processes, documents,
organisational — with a visible decision trail. One list: `CH_ChangeRequest`.
Anyone can submit (a submit-only permission level); change managers triage,
decide and track implementation; days-to-decision is calculated.

**The value case.** Change requests scattered across email, chat and
corridor conversations mean decisions nobody can find and changes nobody
approved. A single register gives requesters a place that isn't someone's
inbox, gives approvers a queue instead of an archaeology project, and gives
auditors the thing they always ask for: who approved this change, when, and
why. It spans every function because every function changes things.

**Five declared views**, deployed with the paste — nothing to build by
hand: *In flight* (the default), *Triage queue*, *Awaiting decision*
(grouped by approver), *Approved, not yet implemented*, *Decision log*.
`DaysToDecision` renders as a bar against the slowest SLA, coloured by the
urgency it was supposed to meet — so twelve days reads as fine on a Routine
change and as a failure on an Emergency one.

**The New form is the submit-only intake made visible.** Impact, status,
approver and every decision field are off it; a requester describes the
change and says how urgent it is. The decision fields appear as the status
moves, so the save rules fire with the field they name on screen.

**Work the folders in order:**

| Step | Folder | You |
|---|---|---|
| 1 | `10-design/` | Fit change types and impact language to your org |
| 2 | `20-configure/` | Prefix; the submit-only intake model |
| 3 | `30-deploy/` | Administrator: build, paste, verify the intake level |
| 4 | `40-adopt/` | Requesters' guide + change managers' guide |
| 5 | `50-govern/` | Decision authority by impact, SLAs, emergency changes |

**Customisation points:** `ChangeType` enum; the decision-authority table in
governance (who may approve what) — the register records authority, it
doesn't enforce it; and the `max:` on the `DaysToDecision` bar, which ships
set from the slowest SLA in that table.

**Demo data.** Build with `--seed` and the bundle gains a `demo-data.js.txt`
that pastes six `[DEMO] `-titled rows — two in triage, one under review,
one approved and stalled past sixty days, one emergency decided in a day
and one rejected after three weeks — so every view and every colour band
renders on a first look. See `30-deploy/deploy.md`.
