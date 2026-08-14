# Audit actions

Audit findings and the recommendations they produced, tracked to closure
with evidence. Two lists: `AU_Audit` (each review: internal, external,
accreditation) and `AU_Recommendation` (linked findings/recommendations,
each with an agreed action, owner, due date and closure evidence).

**The value case.** "Where are we up to on the audit recommendations?" is
the question every audit committee asks and every organisation answers
badly from spreadsheets. This register makes the answer a view, and
**seven of them deploy with the lists**: open recommendations by owner,
overdue against the *committed* date (the revised one where a formal
extension exists), the evidence-verification queue, the committee pack
grouped by audit, and recent closures showing how late each one was.
External auditors consistently rate recommendation-tracking maturity.
This is the cheapest maturity point you'll ever buy.

A recommendation cannot be closed without both the evidence link and the
closure date, and `DaysLate` takes its colour from the finding's own
rating, so a forty-day-late Critical does not look like a forty-day-late
Low. Build with `--seed` and eleven demo rows show every view, every
colour and both branches of the overdue filter before you load a thing.

**Work the folders in order:**

| Step | Folder | You |
| --- | --- | --- |
| 1 | `10-design/` | Fit audit types and finding ratings to your assurance map |
| 2 | `20-configure/` | Prefix; audit-team-maintains security |
| 3 | `30-deploy/` | Administrator: build, paste, verify; load the backlog |
| 4 | `40-adopt/` | Action owners' guide + audit coordinator guide |
| 5 | `50-govern/` | Closure evidence rules, committee reporting, overdue escalation |

**Customisation points:** `AuditType` and `FindingRating` enums; the
closure-evidence standard in governance (what "done" must prove).
