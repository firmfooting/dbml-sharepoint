# Grants register

*Theme: governance, risk & compliance — built for organisations that chase
funding (regional health, community services, education, research).*

Every funding submission from preparation to outcome, and — the part
everyone drops — every **post-award obligation** with its due date. Two
lists: `GR_Submission` (each application: funder, amount, outcome,
agreement) and `GR_Acquittal` (linked reporting/acquittal obligations,
each with a deadline and evidence).

**The value case.** Organisations are good at the adrenaline phase
(finding rounds, writing bids) and terrible at the obligations phase —
the mid-term report due in 14 months is remembered by exactly nobody the
week it's due. Missed acquittals damage the relationship that wins the
*next* grant. This register keeps the submission pipeline visible and
turns post-award obligations into a due-date view, loaded once from each
funding agreement on the day it's signed.

**Nine views deploy with the lists** — a pipeline, live grants, the funder
relationship file and a lost-bids shelf on one side; open obligations,
*Due 90 days*, *Overdue*, *By grant* and a filed history on the other. An
overdue obligation tints its whole row. A successful bid cannot be saved
without the awarded amount, and a filed obligation cannot be saved without
the date it was filed. Build with `--seed` and eleven demo rows show every
view, every colour and the overdue wash working before you load a thing.

**Work the folders in order:**

| Step | Folder | You |
| --- | --- | --- |
| 1 | `10-design/` | Fit outcome/obligation language to your funders |
| 2 | `20-configure/` | Prefix; grants-team-maintains model |
| 3 | `30-deploy/` | Administrator: build, paste; load live grants + obligations |
| 4 | `40-adopt/` | The sign-then-load habit; the obligations sweep |
| 5 | `50-govern/` | Bid/no-bid discipline, acquittal escalation, funder relations |

**Customisation points:** outcome vocabulary; whether unsuccessful bids
are analysed (governance says yes — they're purchased market intelligence).
