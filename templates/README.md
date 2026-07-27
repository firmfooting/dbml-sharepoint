# Solution templates

Ready-to-deploy SharePoint list solutions for common business processes.
Each template is a complete, working input set for `dbml-sharepoint build`
**plus** the organisational material a real rollout needs: an administrator
deployment guide, staff education, and governance resources.

The library is organised into four themes, plus sector guides
(currently: [regional healthcare](HEALTHCARE.md) — NSQHS mapping,
statutory-system boundaries, and a first-90-days sequence). Templates interconnect across
themes by *process hand-off* (documented in their governance files), never
by list lookups — every template deploys and stands alone.

## Theme: Process digitisation & improvement

The improvement engine: inventory your processes, digitise the painful
ones, measure what matters, and close the loop.

| Template | Process | Highlights |
|---|---|---|
| [process-register](process-register/) | Business-process inventory | The digitisation backbone — calculated digitisation-priority score (criticality × pain) |
| [improvement-register](improvement-register/) | Continuous improvement log | Idea → test → adopt/abandon stages; before/after measures; fed by complaints, incidents and audits |
| [measures-register](measures-register/) | KPI / measures catalogue | Definitions with numerator/denominator discipline — makes "improved" provable |
| [project-pipeline](project-pipeline/) | Project ideas to decisions | Calculated benefit×feasibility priority score; gate + graveyard discipline |
| [change-register](change-register/) | Change requests & approvals | Submit-only intake, decision authority trail, days-to-decision |

**The digitisation journey, using this theme:** inventory processes and
score the pain (*process-register*) → deploy quick-win templates or build
your own schema for the worst ones → define how you'll know it worked
(*measures-register*) → run the smaller fixes as improvement cycles
(*improvement-register*) and the bigger ones through *project-pipeline* /
*change-register*.

## Theme: Governance, risk & compliance

| Template | Process | Highlights |
|---|---|---|
| [risk-register](risk-register/) | Organisational risk | **Self-rating 5×5 matrix** — rating and score calculated, matrix-inconsistent entries impossible |
| [audit-actions](audit-actions/) | Audit recommendations to closure | Closure-evidence standard, guarded DaysLate metric, committee-pack view |
| [declarations-register](declarations-register/) | Conflicts of interest + gifts & benefits | Two standalone compliance lists; declare-only staff level |
| [policy-library](policy-library/) | Policies & controlled documents | Document library with draft/published minor versions, review register |
| [contract-register](contract-register/) | Contracts & renewals | Calculated term length, renewal pipeline views |
| [compliance-obligations](compliance-obligations/) | Legislation / standards / funding obligations | The accreditation backbone: obligation → owner → evidence → review |
| [grants-register](grants-register/) | Funding submissions & acquittals | The post-award obligations everyone else drops, as a due-date view |
| [delegations-register](delegations-register/) | Who may approve what | The searchable mirror of your instrument of delegation — the lookup every other register's "per your delegations" points at |

## Theme: Operations & service

| Template | Process | Highlights |
|---|---|---|
| [service-requests](service-requests/) | Internal helpdesk (facilities/IT/admin) | Per-team queues from one intake; highest goodwill-per-hour in the set |
| [incident-management](incident-management/) | Incidents & corrective actions | Two linked lists, report-only staff permission level |
| [complaints-feedback](complaints-feedback/) | External complaints & feedback | Two calculated response clocks; no-members-access privacy posture |
| [asset-register](asset-register/) | Equipment / IT assets | Location lookup, unique asset tags, assignment tracking |
| [equipment-maintenance](equipment-maintenance/) | Testing / preventive maintenance | Next-due schedule with evidence-linked history; the Overdue view's target is empty |
| [routine-checks](routine-checks/) | Digitised paper checklists | Fridge temps, trolley checks, rounds — timestamped, attributed, acted on |
| [switchboard-log](switchboard-log/) | Switchboard / after-hours desk | The three paper books digitised: code log (calculated duration), message book (relay times), key register |
| [visitor-log](visitor-log/) | Front-desk sign-in | An On-site-now view (which you create — see its DEPLOY.md) becomes the evacuation muster list; contractor induction flag |
| [vehicle-log](vehicle-log/) | Pool-car log books | Calculated kilometres from odometer readings; the Purpose column is your FBT substantiation |

## Theme: People & relationships

| Template | Process | Highlights |
|---|---|---|
| [meeting-actions](meeting-actions/) | Meetings, decisions, actions | The fastest payback in the library — deploy before your next meeting |
| [onboarding-tracker](onboarding-tracker/) | New-starter coordination | HR + IT + facilities + finance queues from one record |
| [training-register](training-register/) | Training & certification compliance | Course catalogue + per-person records, expiry tracking |
| [stakeholder-contacts](stakeholder-contacts/) | External relationships & interactions | CRM-shaped without CRM weight; privacy governance included |
| [credentialing-register](credentialing-register/) | Practitioner credentials & scope of practice | Who may do what, on whose decision, until when — with evidence |
| [volunteer-register](volunteer-register/) | Volunteers & their checks | Police/WWCC expiry sweeps; privacy-first, no general access |

## Anatomy — every template follows the same sequence

```
<template>/
  README.md            Why this exists, the value case, what to customise
  10-design/           The data model
      schema.dbml        — tables/columns/enums (render the ERD on dbdiagram.io)
  20-configure/        The physical and release configuration
      mapping.yaml       — prefix, indexes, versioning, formulas, security model
      release.yaml       — the version stamped into every deployed artefact
      formatting/        — optional; formatter JSON referenced by mapping.yaml
  30-deploy/           Administrator guidance
      DEPLOY.md          — build, paste, verify; template-specific checks
  40-adopt/            Staff education
      STAFF-GUIDE.md     — day-to-day usage in plain language
  50-govern/           Governance resources
      GOVERNANCE.md      — ownership, review cadence, data quality, lifecycle
```

Work the folders in order: **design** what you're deploying (rename columns,
prune what you don't need), **configure** it for your site (prefix, security),
**deploy** it (administrator), **adopt** it (staff), **govern** it (owners).

**Notes are form text.** A column's `note:` deploys as the SharePoint column
Description, which the modern list form shows as help text under the input at
data-entry time — so every note is written as a plain-language hint for the
person filling in the form ("Calculated automatically…", "Filled
automatically: … Leave as-is."). Design rationale and mechanics live in `//`
comments beside the columns, which never deploy. When you customise a
template, keep that split: if it isn't something a staff member should read
on the form, it belongs in a comment, not a note.

**Formatter JSON: inline or referenced.** Anywhere `mapping.yaml` takes a
formatter object — `column_formatting` overrides, `views[].formatting`, and
each `form_formatting` part — it accepts either an inline mapping or a
relative path to a `.json` file, resolved against `20-configure/`. Keep short
formatters inline where they read as part of the declaration; put long ones
(a multi-section form body, a bespoke row formatter) in
`20-configure/formatting/` so `mapping.yaml` stays readable. Both forms
deploy identically. The directory is optional — omit it when every formatter
is inline.

## Deploying any template (shared procedure)

From the repository root — substitute the template name and your site:

```bash
dbml-sharepoint build \
  --schema templates/<name>/10-design/schema.dbml \
  --mapping templates/<name>/20-configure/mapping.yaml \
  --release templates/<name>/20-configure/release.yaml \
  --site-url https://yourtenant.sharepoint.com/sites/your-site \
  --site-role default \
  --out ./build
```

1. **On a new site, assess first.** Every build emits `build/assess.js`;
   paste it from the target site's console (it is read-only). The
   `[SP-ASSESS] [DONE]` verdict must be **COMPATIBLE** or an accepted
   **DEGRADED**; a **BLOCKED** verdict means fix the site (or the
   operator's rights) before deploying. See `build/assess-manifest.md`.
2. **Read `build/deploy-manifest.md`.** It opens with step-by-step run
   instructions and must show **0 validation errors**.
3. Open the target site's classic settings page
   (`/_layouts/15/settings.aspx`) signed in as a **Site Owner**, press F12 →
   Console (type `allow pasting` if the browser objects), paste the whole of
   `build/deploy.js`, Enter.
4. Watch the `[SP-DEPLOY]` lines; success ends with `errors: []`. On any
   error: read it, fix the stated cause, paste the same script again —
   reruns verify-and-skip completed work.
5. Complete the template's own `30-deploy/DEPLOY.md` verification checklist.
6. Create the views listed under **Recommended views** in that DEPLOY.md.

**Recommended views are not deployed — you create them.** No template
declares a `views:` block, so a fresh deploy gives each list SharePoint's
default *All Items* view and nothing else. Every "Recommended views" table
is a specification for views you build in the SharePoint UI (or add to
`mapping.yaml` under [`views:`](../website/docs/reference/mapping.md#views)
and redeploy, which is the reproducible option). Nothing in a template's
DEPLOY, STAFF-GUIDE or GOVERNANCE file will work until you have made them —
so make them before you hand the list to anyone, and treat any document
that names a view as depending on that step.

## The shared security model

Unless a template says otherwise: ordinary **site Members work with items
and cannot break the lists** (no schema or permission rights), working
groups carry the process-specific access, and an **empty-by-default
`* List Administrators` group holds Full Control** — the deploy script
enrols the running operator into it for the duration of the run and removes
them afterwards, so schema changes and redeploys are deliberate acts, not
accidents. Every list uses `reconcile: exact`: undeclared permission grants
are removed on deploy and redeploy.

### Hardening and drift detection

Every template opts into the deployer's UI hardening: **all deployed
columns are sealed** (SharePoint refuses UI schema edits and deletion of
sealed columns, even for site admins — the deploy script unseals for its
own run and re-seals, with verification, in Phase 4.1) and **every list
carries `AllowDeletion = false`** ("Delete this list" disappears for
everyone). `rollback.js` stays usable: it clears the deletion block per
list only after you confirm that list's deletion, and restores the block
if a delete fails. This is friction + tamper-evidence, not enforcement —
a site collection admin can flip both back via API, and a redeploy
re-asserts sealing and the deletion block and reports having done so.

Two things remain possible on a sealed column, and the deployer treats
them very differently:

- **Display-name renames.** Detected: reverted and reported on the next
  re-paste.
- **Hiding it from the forms** via "Edit form → Edit columns". **Not
  detected and not repaired.** That toggle writes the content type's
  `FieldLink.Hidden` rather than anything on the field, so field-level
  sealing never covered it — and nothing in the deployer reads, writes,
  probes or reports that property. A redeploy runs clean and says nothing.
  The repair is manual: re-tick the column in the same "Edit columns"
  panel. It cannot be scripted through the REST surface these scripts
  use — `FieldLink.Hidden` is writable only through CSOM, which is why
  declared form behaviour deliberately uses a different mechanism (see
  below).

**Declared form visibility is detected.** `form_visibility:` and
`column_validation:` in `mapping.yaml` write field properties, not field
links, and those *are* read back, compared and reverted on every deploy.
So a column whose visibility you declared is protected; a column somebody
hid by hand through the designer is not. The two states look identical to
someone filling in the form, which is the argument for declaring the
behaviour you want rather than leaving it to whoever last opened the
designer. See
[the mapping reference](../website/docs/reference/mapping.md#form_visibility).

**One open question, recorded rather than answered.** A site that was
deployed by an older version of this tool using the removed
`hidden_on_forms:` key has SchemaXml `ShowIn*Form` attributes that the
current deployer neither writes nor clears. A column can therefore stay
hidden because of a setting no current declaration mentions, while the
manifest reports its formula as cleared. Whether the deployer should clear
those attributes once on migration is a real decision — it is a write to a
property the tool has otherwise stopped touching, on sites whose operators
did not ask for it — and it has not been made. If you are migrating such a
site, check the affected columns in the form designer by hand.

Detection is continuous on the reporting side: every generated reporting
bundle ships `_UserAddedColumns.pq` (reads each list's live field
metadata on refresh; expected EMPTY — any row is a column added outside
the template) and `vw_<prefix>UserAddedColumns` (the same audit over
warehouse-landed tables). Load the audit query alongside the dictionary
queries and keep it on the report's documentation page.

Status columns across the templates render as SharePoint's own severity
boxes with icons per the deployer's style standard (see
[the style guide](../website/docs/reference/style-guide.md)) — consistent colours and
iconography fleet-wide, using only Microsoft's documented formatting
classes.

## Customising before you deploy

- **Prefix** (`mapping.yaml`): pick something short and unique per site —
  two lists with the same internal name cannot coexist.
- **Columns**: delete what you won't use *before* first deploy; removing a
  column later is a manual SharePoint operation.
- **Choices**: edit enum members in `schema.dbml` to your organisation's
  vocabulary now — renaming a choice later strands existing rows on the old
  value.
- **Security**: group names and levels live in `mapping.yaml`; the
  governance doc in each template explains who is intended to hold what and
  why.
