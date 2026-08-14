# Training register

Who is trained in what, when it was done, and when it expires. Two lists:
`TR_Course` (the catalogue of trainings/certifications your organisation
requires) and `TR_TrainingRecord` (one row per person per completion, with
expiry).

**The value case.** Training compliance fails quietly: certificates expire,
inductions get skipped for "temporary" staff, and the first time anyone
checks is after the incident. A register makes the two questions instant:
*who is currently covered for X?* and *whose coverage lapses in the next
60 days?*, per record, filterable, exportable for the auditor.

**Deploys with:** seven views (a catalogue grouped by category, the
mandatory subset, the never-expires audit, and (on records) coverage by
person, the 60-day sweep window, coverage by course and the expired list),
sectioned forms on both lists, expiry dates that turn red past due, three
save rules, and eleven demo rows including a lapse and its refresher as
the two separate rows the register insists on.

**Work the folders in order:**

| Step | Folder | You |
| --- | --- | --- |
| 1 | `10-design/` | Fit categories and validity language to your framework |
| 2 | `20-configure/` | Prefix; who maintains records (default: coordinators) |
| 3 | `30-deploy/` | Administrator: build, paste, verify; seed the catalogue |
| 4 | `40-adopt/` | Coordinators' guide + what staff can expect |
| 5 | `50-govern/` | Mandatory-training matrix, expiry monitoring, evidence rules |

**Customisation points:** `Category` enum; whether staff record their own
completions (default: no, coordinators do, because records = evidence).
