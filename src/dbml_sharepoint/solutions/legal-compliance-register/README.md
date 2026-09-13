# Legal compliance register

*Theme: governance, risk & compliance.*

Every compliance topic with its owner, and a library holding one SAQ file
per topic per period: due, answered, confirmed, recorded back. One list,
`LC_Topic`, and one document library, `LC_SAQ`, the first library in the
collection.

**The value case.** A compliance portal issues a self-assessment
questionnaire (SAQ) per legal topic and re-issues it each quarter; Comply
Online, Law Compliance's portal, is the worked example. A health service
typically holds a handful of named portal licences, so the business owners
who actually answer the questions cannot log in, and the usual workaround
is a shared generic login that nobody can audit. This family replaces it.
A coordinator files each period's SAQ into a SharePoint library, the
business owner completes it under their own name, the executive responsible
confirms the result, and a licence holder re-keys it into the portal. The
library carries the workflow columns on the file, so named identity in
SharePoint is the audit trail, and the loop is closed only when a recording
date is set on the file.

**Five views deploy with the library.** *Pending* is the default:
everything not yet Complete, grouped by division and due date first, so a
finished SAQ drops out of sight. *My responsibility* and *My
accountability* are the two personal worklists, *Overdue* is what the
coordinator chases, and *To record in the portal* is the loop-closing
view, where empty is the healthy state. Every one of them is recursive, so
a file is found whichever division folder it was filed in. Three more
deploy with the topic register: *Active topics*, *By business owner* and
*Retired*. Save rules refuse a Submitted or Complete SAQ without a result,
a Complete one without a completed date, and anything past Required
without a division and a due date. Build with `--seed` and six demo files
across the four folders show every status colour and every view working
before you file a thing.

**REG items live here too.** The portal issues regulatory register items
beside the questionnaires; they are filed in the same library with `Type`
set to `REG`. The library is titled `LC_SAQ` rather than something longer
because a list title carries no spaces and is frozen into the URL at
creation.

**Folders.** The library deploys with one root folder per division,
matching the `division` enum name for name:

| Folder | Holds |
| --- | --- |
| `Clinical services` | SAQs for topics the clinical divisions own |
| `Corporate services` | Finance, procurement, workforce and facilities topics |
| `Community services` | Community, home care and outreach topics |
| `Executive and governance` | Board, executive and whole-of-organisation topics |

**Work the folders in order:**

| Step | Folder | You |
| --- | --- | --- |
| 1 | `10-design/` | Fit the divisions and committees to your organisation |
| 2 | `20-configure/` | Prefix; folders to match the divisions; calendar or financial-year quarters |
| 3 | `30-deploy/` | Administrator: build, paste; the manual library settings; load the topics |
| 4 | `40-adopt/` | Filing, completing, confirming and recording, one role at a time |
| 5 | `50-govern/` | Assessment standard, separation of duties, register changes, the drift audit |

**Customisation points:** the `division` and `committee` enums in
`10-design/schema.dbml`, remembering that `entities.SAQ.folders` in
`mapping.yaml` must change with `division`, name for name; calendar versus
financial-year quarters. The shipped `default_formulas` fill calendar
quarters (Q1 is January to March). For a July to June financial year
replace them with `PeriodYear: "=YEAR(TODAY())+IF(MONTH(TODAY())>=7,1,0)"`
(the year the financial year ends in) and
`Quarter: "=\"Q\"&(MOD(ROUNDUP(MONTH(TODAY())/3,0)+1,4)+1)"` (July to
September is Q1), and change the `Quarter` column note and the file naming
convention in `40-adopt/staff-guide.md` to match. That pair has the same
shape as the shipped one and has not been run on a live site. The number
of licence holders is a fact about your portal subscription, not about this
family; `LicenceHolder` on each topic records which named login records
its results.
