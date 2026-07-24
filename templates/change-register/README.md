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
doesn't enforce it.
