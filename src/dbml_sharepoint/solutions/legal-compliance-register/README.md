# Legal compliance register

*Theme: governance, risk & compliance.*

One document library, **Legislative Compliance**, holds vendor-issued Excel SAQs
and the REG workbooks people consult while answering it. There is no separate
topic list. Library columns track assignment and handoffs; responses,
compliance ratings, risk, controls, gaps and evidence remain in Excel for
Power Query and Power BI to read.

## The workflow

1. The platform owner downloads an SAQ from the vendor platform and uploads it
   into the executive's division folder,
   identifies the topic and assigns that executive.
2. The executive assigns the business owner and decides whether executive
   review is required before portal recording.
3. The business owner completes the Excel workbook, sets **Completed date**
   and changes **Status** to *Complete*.
4. If review was requested, the executive checks the workbook and sets
   **Reviewed date**. Otherwise the completed SAQ is ready for recording.
5. The platform owner records the assessment in the compliance platform and
   sets **Recorded in portal**.

These are three roles. Executive review is optional; completion and portal
recording are separate milestones. Role assignments guide the worklists;
permissions do not restrict individual workflow transitions to a role.

## Documents and assessment identity

**SAQ** means self-assessment questionnaire. Download it from the vendor platform
and update that file. Users do not create SAQs or reuse an earlier questionnaire.
A new SAQ for the same topic has a new vendor period. Preserve the vendor's
filename and issuance label, for example:

`SAQ - VIC - Health Privacy Principles [Q3-2023].xlsx`

**Issued year** and **Issued quarter** describe the publisher's original
issue, 2023 and Q3 in that example. They never default from today's date.
The file itself identifies the assessment; completion dates describe your work.
Keep successive vendor issues as separate files without overwriting earlier work.

**REG** means the accompanying regulatory reference workbook. File it with
**Type** set to *REG*. It has no completion, executive-review or recording
workflow. Keep the publisher's filename, for example:

`REG - VIC - Health Privacy Principles [Q3-2023].xlsx`

Both files carry the same **Portal topic ID** from the workbook and the same
**Topic name**, including jurisdiction. The ID is intentionally not unique:
references and successive assessments share it. Match the reference issue to
the SAQ being answered; two files sharing a topic need not share an issue.

## Division folders

The four example folders are **Clinical services**, **Corporate services**,
**Community services** and **Executive and governance**. Customise them in the
DBML `division` enum alone: the folders are its members and the mapping keeps
no second list. The platform owner assigns the executive according to the
folder. The bundle does not automate that person assignment or delegation.

Each folder has its own permissions. The deploy creates one
`{prefix} <division> Division` group per member and breaks the folder's
inheritance, so edit inside a division folder belongs to that division's
group, **{prefix} Compliance Coordinators** and **{prefix} Assessment
Owners**, with **dbml List Administrators** at Full Control and site members,
site owners and **dbml Enterprise Readers** keeping Read. The division groups
add per-division delegation; they do not remove the register-wide roles this
family already declares.

A grant made at library scope no longer reaches files inside a division
folder, so any role that needs to edit there has to appear in the folder
policy as well. That is why Assessment Owners is listed above.

Each division group is declared with the coordinators as its `owner_group`.
The intent is that coordinators can move people between divisions without
holding site Full Control. **That delegation is not yet verified.** Whether a
group owner who is not a site administrator can actually edit that group's
membership is the question `test/manual/library-sharing-probe.js` asks, and
the probe has not been run against a live site. Until it has, plan on a site
administrator maintaining the division groups.

Sharing a file directly out of a folder is also **not characterised**. The
same probe asks what a direct share changes at file and folder scope and has
not answered it, so treat what a recipient of a shared file can do as unknown
rather than as governed by the groups above.

## Worklists

| View | Purpose |
| --- | --- |
| Platform owner | Flat, unfiltered SAQs and REGs across all folders, recently modified first |
| Pending | SAQs Required or In progress, recently modified first |
| My responsibility | Open SAQs assigned to the current business owner |
| My accountability | The executive's SAQs awaiting completion, review or recording |
| Awaiting review | Complete SAQs with requested review still outstanding |
| To record in the portal | Complete SAQs ready for recording, with no recording date |
| Recorded assessments | Complete SAQs recorded in the portal |
| Reference regulations | REG files without assessment workflow columns |
| All assessments | All SAQs, including completed and cancelled assessments |

Every view searches across the division folders. Build with `--seed` for
nine synthetic demonstration files covering every worklist, including
successive vendor periods for one topic and both review routes.

## Adopting version 2

This is a breaking replacement for version 1's `LC_Topic` list and `LC_SAQ`
library. It creates **Legislative Compliance** at `LegislativeCompliance`;
it does not convert, delete or migrate
those existing containers. Keep them until files, ownership and history
have been reconciled with the new library. See [deployment](30-deploy/deploy.md).

During migration, transfer only identity, assignment and tracking metadata.
Assessment answers and findings stay in the SAQ files. Resolve duplicate topics
and missing owners before assigning records. No organisation-specific sample
files or identities are included in the shipped template.
