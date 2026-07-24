# Policy library

Controlled documents with a review discipline. Two components:
`PL_PolicyDocuments` — a **document library** with draft/published
versioning (minor versions on) — and `PL_PolicyRegister`, the list that
gives every policy an owner, a status and a next-review date.

**The value case.** The failure mode of policy management is silent
staleness: documents nobody owns, reviews nobody schedules, staff following
a version that was superseded two years ago. The register makes review
dates a filterable fact; the library's major/minor versioning separates
what staff see (published, 1.0/2.0) from what authors are drafting
(1.1, 1.2 …).

**Work the folders in order:**

| Step | Folder | You |
|---|---|---|
| 1 | `10-design/` | Fit policy areas and statuses to your framework |
| 2 | `20-configure/` | Prefix; who may author vs. who may read |
| 3 | `30-deploy/` | Administrator: build, paste, verify library versioning |
| 4 | `40-adopt/` | Staff: where the current policy is; authors: draft → publish |
| 5 | `50-govern/` | Review cadence, approval rules, register-library sync |

**Customisation points:** `PolicyArea` enum (align to your policy
framework's domains); review interval defaults are governance, not schema.
