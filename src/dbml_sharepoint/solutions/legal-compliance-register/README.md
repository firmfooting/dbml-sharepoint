# Legal compliance register

*Theme: governance, risk & compliance.*

One document library, `LC_Document`, holds a new Excel SAQ for each assessment
and the REG workbooks people consult while answering it. There is no separate
topic list. Library columns track assignment and handoffs; responses,
compliance ratings, risk, controls, gaps and evidence remain in Excel for
Power Query and Power BI to read.

## The workflow

1. The platform owner uploads a new SAQ into the executive's division folder,
   identifies the topic and assessment, assigns that executive and sets a due
   date. The platform owner also names themselves on the assessment.
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

**SAQ** means self-assessment questionnaire. Each assessment has a new file,
even when the publisher has not revised its questionnaire. Use an assessment
reference in both the filename and **Assessment reference**, for example:

`SAQ - VIC - Health Privacy Principles [Q3-2023] - assessment-2026-01.xlsx`

**Issued year** and **Issued quarter** describe the publisher's original
issue, 2023 and Q3 in that example. They never default from today's date.
The assessment reference, due date and completion date describe your work.
Do not overwrite an earlier assessment to start a later one.

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
**Community services** and **Executive and governance**. Customise these to
the organisation's executive divisions in both the DBML enum and mapping.
The platform owner assigns the executive according to the folder. The
bundle does not automate that person assignment or delegation. These folders
currently inherit library permissions; they do not yet isolate division access.

## Worklists

| View | Purpose |
| --- | --- |
| Platform owner | Flat, unfiltered SAQs and REGs across all folders, recently modified first |
| Pending | SAQs Required or In progress, earliest due first |
| My responsibility | Open SAQs assigned to the current business owner |
| My accountability | The executive's SAQs awaiting completion, review or recording |
| Overdue | Open SAQs past their due date |
| Awaiting review | Complete SAQs with requested review still outstanding |
| To record in the portal | Complete SAQs ready for recording, with no recording date |
| Recorded assessments | Complete SAQs recorded in the portal |
| Reference regulations | REG files without assessment workflow columns |
| All assessments | All SAQs, including completed and cancelled assessments |

Every view searches across the division folders. Build with `--seed` for
nine synthetic demonstration files covering every worklist, including
repeated assessments of one topic and both review routes.

## Adopting version 2

This is a breaking replacement for version 1's `LC_Topic` list and `LC_SAQ`
library. It creates `LC_Document`; it does not convert, delete or migrate
those existing containers. Keep them until files, ownership and history
have been reconciled with the new library. See [deployment](30-deploy/deploy.md).

The supplied tracking workbook is current-state source data. Import only
identity, assignment and tracking metadata; assessment answers and findings
stay in the workbooks. Resolve duplicate topic rows and missing owners before
assigning records. No organisation-specific sample files or identities are
included in the shipped template.
