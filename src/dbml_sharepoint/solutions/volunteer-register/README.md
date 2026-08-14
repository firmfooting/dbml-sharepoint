# Volunteer register

*Theme: people & relationships, built for organisations that run on
volunteers (regional healthcare, aged care, community services, sport).*

Every volunteer, their role, and the compliance that keeps them (and the
people they serve) safe: police check and Working with Children Check
expiries, induction status, and an honest active/inactive picture. One
list: `VL_Volunteer`.

**Deploys with:** five views (the team roster, the 90-day expiry sweep, a
missing-checks surface, the applicant pipeline and the retention list), a
sectioned form whose Start Date only appears once the volunteer is off
Applying, expiry dates that turn red past due, two save rules, and six
demo rows so the whole thing is visible the minute you paste it.

**The value case.** Volunteers arrive through goodwill and stay off the
HR system, which means their checks live in a drawer and their expiry
dates live nowhere. For services working with patients, elders or
children, an expired WWCC isn't paperwork; it's a reportable governance
failure. The register makes the expiry sweep a monthly filter, the
"how many active volunteers do we have?" question answerable, and the
insurance/funding-body return a view instead of a hunt.

**Privacy posture:** volunteer records are personal data: ordinary site
members get **no access**; coordinators maintain. Scope the site
accordingly.

**Work the folders in order:**

| Step | Folder | You |
| --- | --- | --- |
| 1 | `10-design/` | Fit roles/check vocabulary to your programme |
| 2 | `20-configure/` | Prefix; coordinators-only model |
| 3 | `30-deploy/` | Administrator: build, paste; load current volunteers |
| 4 | `40-adopt/` | Coordinators' guide: onboarding, sweeps, exits |
| 5 | `50-govern/` | Check requirements by role, privacy, retention |

**Customisation points:** which checks are mandatory per role: the matrix
in governance; jurisdictions differ (WWCC/Blue Card/WWVP), rename to yours.
