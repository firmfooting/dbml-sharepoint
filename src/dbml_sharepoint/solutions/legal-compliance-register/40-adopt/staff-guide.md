# Legal compliance register: guide

## What this is

One library, `LC_SAQ`, holding one file per topic per period with the
assessment workflow on the file's panel, and one register, `LC_Topic`,
saying who owns each topic. Only the licence holders log in to the
compliance portal. Everybody else works in the library, under their own
name, which is the whole point: the library is the audit trail the shared
portal login never was.

## The views

The library opens on **Pending**. Four other views are already built for
you, and every one of them finds files in every division folder, so where a
file was filed never hides it:

| View | What it shows |
| --- | --- |
| **Pending** | The default. Everything not yet Complete, grouped by division, earliest due date first. A finished SAQ drops out. |
| **My responsibility** | SAQs where you are the business owner and the status is *Required* or *In progress*. |
| **My accountability** | SAQs where you are the executive responsible and the status is not Complete, *Submitted* first. |
| **Overdue** | Past its due date and not Complete. The coordinator's chase list. |
| **To record in the portal** | Confirmed by the executive and not yet recorded in the portal. Empty is the healthy state. |

The topic register has three: **Active topics** (grouped by division),
**By business owner** and **Retired**. You don't need to build any of
these, and you shouldn't rename them: a redeploy puts the declared name
back.

The library syncs read-only through the OneDrive client, because Microsoft
synchronises any library with validation columns or metadata that way, so
open files from the library in the browser rather than from a synced
folder.

## Coordinators: filing a period's SAQs

1. A licence holder downloads each topic's SAQ from the portal.
2. Save it into the topic's division folder as `<Topic> - <Year> Q<n>`,
   for example `Food safety - 2026 Q2.docx`. The quarter is the calendar
   quarter (Q1 is January to March).
3. Fill the panel at upload: **Topic**, **Division** (the folder you
   chose), **Business owner** and **Executive responsible** copied from the
   topic row, and **Due date**. **Period year** and **Quarter** are
   pre-filled with the current period; change them only for a SAQ filed
   after its quarter ended, and check them on the first day of a quarter.
4. Leave **Status** at *Required*. The register will not let anyone move
   it past *Required* without a division and a due date.

A regulatory register item from the portal is filed the same way, with
**Type** set to *REG*.

## Business owners: completing a SAQ

Open **My responsibility**. Set **Status** to *In progress* so the
coordinator can see it has started. Open the file, answer it, and save it
back into the library so the version history holds your work. Set
**Compliance** to what the evidence supports (*Compliant*, *Partially
compliant* or *Non-compliant*), say in **Notes** what evidence you sighted,
and set **Status** to *Submitted*. The register will not accept *Submitted*
with **Compliance** still at *Not assessed*.

You never log in to the portal. *Partially compliant* and *Non-compliant*
are safe to say; a gap raised is an action, a gap hidden is a finding.

## Executives: confirming a result

Open **My accountability**. Submitted SAQs sort to the top. Open the file
and check the result against it, not against the panel. For a *Partially
compliant* or *Non-compliant* result, agree the action with the business
owner, record it on the audit actions or improvement register, and paste
its link into **Action link**, which appears on the panel once the result
is a gap. Set **Completed date** to today and **Status** to *Complete*.
The SAQ leaves **Pending** and your worklist, and appears in **To record
in the portal**. The register will not accept *Complete* without a
completed date.

If you completed the SAQ yourself, you do not also confirm it. Ask the
compliance owner to.

## Licence holders: recording in the portal

Open **To record in the portal**. For each file, key the answers and the
rating into the portal under your own named login, then set **Recorded in
portal** to the day you did it. The file drops out of the view. When the
view is empty, every confirmed result is in the portal.

## The form

The panel has four sections, in the order the work happens: **The SAQ**
(which topic and period, which folder, when it is due), **Complete it**
(the business owner's half), **Confirm it** (the executive's half) and
**Record in the portal** (the licence holder's date). Per-field hints show
on the New form only; SharePoint hides column descriptions on the Edit
form.

## When a topic changes hands

Tell the coordinators, then, not at the next quarter. They update the
topic row and the open SAQs together (`50-govern/governance.md` says how),
because the owners on a SAQ are a copy of the register's and do not follow
it on their own.
