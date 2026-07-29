# Policy library

Controlled documents with a review discipline. Two components:
`PL_PolicyDocuments` — a **document library** with draft/published
versioning (minor versions on) — and `PL_PolicyRegister`, the list that
gives every policy an owner, a status and a next-review date.

**The value case.** The failure mode of policy management is silent
staleness: documents nobody owns, reviews nobody schedules, staff following
a version that was superseded two years ago. The register makes review
dates a filterable fact; the library's major/minor versioning separates
published policies (1.0, 2.0) from what authors are iterating on
(1.1, 1.2 …).

**Four register views deploy with the list** — *By area* (the default,
grouped and filtered to policies in force), *Review due*, *In development*
and *Retired* — and an approved or published policy cannot be saved without
the date its review interval is measured from. An **Approved** policy
renders amber rather than green, because a decision staff cannot yet read
is a job half done. Build with `--seed` and six demo policies show every
status and every group heading before you register a real one.

> **The document library is uplifted only as far as its display titles.**
> `views:`, a form body and demo data all describe a *list*, and three of
> them are refused outright on a `DocumentLibrary` — the file name column
> is not addressable from a mapping. `30-deploy/DEPLOY.md` sets out exactly
> what does not fit and leaves the library's one recommended view as a
> manual step.

> **Minor versions alone do not hide drafts from readers.** The deploy
> enables major and minor versioning; it does **not** set *Draft Item
> Security*, which SharePoint leaves at "Any user who can read items". So
> until an administrator changes it by hand, a reader with Read access can
> open a 0.1 draft. `30-deploy/DEPLOY.md` has the one-time step.

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
