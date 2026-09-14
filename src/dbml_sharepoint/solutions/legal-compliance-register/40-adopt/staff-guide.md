# Legal compliance register: guide

## What this is

`LC_Document` contains assessment workbooks (SAQs) and regulatory references
(REGs). Complete the assessment inside Excel. The file's properties track
who is doing it and where it is in the process. Do not copy answers, controls,
compliance ratings, risk or gaps into library properties.

## Platform owners: file and assign

1. Download the SAQ from the vendor platform and upload it into the executive's
   division folder. Preserve its filename and issuance label. A new SAQ for
   the same topic has a new period; users do not create or reuse questionnaires.
2. Set **Type** to *SAQ*. Enter **Topic name**, **Portal topic ID**, **Issued
   year** and **Issued quarter** from the publisher's file. The issuance
   period is not your assessment period and is not filled automatically.
3. Set **Division** and **Executive responsible**. The executive assignment is
   a manual step based on the folder's division. Leave **Status** at *Required*.
4. Upload the supporting REG with **Type** set to *REG* and matching topic
   metadata. Its assessment properties are hidden and it stays out of the
   assessment worklists.

Open **Platform owner** for the flat workspace across every folder, including
SAQs, REGs and files whose metadata still needs completing. It shows recently
modified files first. Use its columns to maintain assignments and handoffs.

Open **Pending** to chase outstanding assessments. Blank owner columns need
assignment, even when the file has otherwise saved successfully.

## Executives: delegate and optionally review

Open **My accountability** and assign **Business owner**. Set **Review
requirement** to *Required* if you want to review the completed SAQ before
it goes to the compliance platform; otherwise leave it *Not required*.
Decide this when assigning the work so the platform owner knows the route.

Completed SAQs needing review appear in **Awaiting review**. Open the Excel
file, check the answers and set **Reviewed date**. If further work is needed,
clear the completion and review dates, then return **Status** to *In progress*.
A correction to a file already recorded in the portal must be coordinated
across the workbook and the platform record.

## Business owners: complete the workbook

Open **My responsibility**, set **Status** to *In progress* and answer the
SAQ in Excel using the REG as reference material. Keep the file in the
library while working. When finished, set **Completed date** and **Status**
to *Complete*. This records your completion, whether or not executive review
was requested. **Tracking notes** are for assignment or handoff comments.

Use the library in the browser. See the deployment guide for the OneDrive
sync limitation affecting libraries with validation.

## Platform owners: record the assessment

Open **To record in the portal**. This contains completed SAQs with either
no review requested or a completed review. Record the workbook in the
compliance platform under your named account, then set **Recorded in
portal**. The file leaves this worklist and appears in **Recorded assessments**.

**All assessments** preserves the full assessment history. **Reference
regulations** holds the REGs. Mark a cancelled SAQ *No longer required*;
keep its file and explain the cancellation in **Tracking notes**.
