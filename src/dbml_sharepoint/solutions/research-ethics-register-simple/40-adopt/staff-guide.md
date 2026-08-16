# Research ethics register: staff guide

*For whoever records ethics and governance decisions. Everyone else can look,
not touch, and looking is the point.*

## What this is

One list (**RG_Project**) with one row per research or quality project this
service refers to a partner HREC. The row answers four questions: what was
approved, by whom, until when, and what is owed now.

**It holds project metadata only.** No participant names, no identifiers, no
clinical detail, and no recruitment or consent counts either, not even
totals. Those belong in the study file or the trial management system. If
something you are about to type is about a *participant* rather than about
the *project*, it does not go here.

## The two gates, which are the whole idea

**Ethics approval** is the partner committee's decision. **Site
authorisation** is ours. Our research governance officer assesses the
site-specific assessment, and the Chief Executive or delegate authorises the
project for this site.

They are two columns because they are two decisions, and the dangerous state
is the one in between: **approved by the committee, not yet authorised
here.** A project in that state cannot start, and it looks exactly like a
project that can unless something says so.

**Site Readiness** is that something. It works itself out from the two gate
columns and you cannot edit it:

| It says | It means |
| --- | --- |
| **Ready to start here** | Both gates cleared. Go. |
| **Ethics cleared - site authorisation outstanding** | The committee said yes; we have not. **Not yet.** |
| **Site authorised - ethics not cleared** | Our paperwork says yes and the committee's does not, including an approval that has quietly expired. The only red in the register. |
| **Neither gate cleared** | Early days. |
| **Not proceeding** | Refused or withdrawn. Ethics Status beside it says which. |
| **Suspended at this site** | Stopped by us. |

If a row is marked **Underway** or **Closed to recruitment** with no site
authorisation, the whole row turns pink in the default view. That is not
decoration. Somebody may be recruiting who should not be, or already has.
Tell the research governance officer the same day; do not fix it by changing
the stage. Closing recruitment does not close the gap, so the wash does not
lift until the authorisation is recorded or the project moves to Completed or
Discontinued.

## The six views

The list opens on **Live projects**: everything not completed or
discontinued. Five other views are already built for you:

| View | What it shows |
| --- | --- |
| **Live projects** | The default. Current work only; closed projects are in Archive. |
| **Ready to start here** | Both gates cleared and not finished. The answer to "may this start?" |
| **Ethics cleared, not authorised** | The gap. Oldest decision first, because the longer one sits here the likelier somebody has assumed otherwise. |
| **Response required** | The ball is in *our* court: either the committee has asked us something, or our own governance office has. |
| **Reports due soon** | Anything due inside the next sixty days. A *rolling* sixty days, not "this quarter". |
| **Archive** | Completed and discontinued projects, most recent first. |

You don't need to build any of these, and you shouldn't rename them: a
redeploy puts the declared name back.

**Why the default is filtered.** This register only grows: five to thirty
projects a year, kept forever. Filtering closed work out of the default view
is what keeps it usable in year ten. Nothing is deleted; it moves to
**Archive**.

## Adding a project (3 minutes)

1. Open the **RG_Project** list -> **New**.
2. **The project**: the **Title** worded as the ethics application words it,
   **Project Type**, **Department**, and the **Principal Investigator** named
   as the application names them (they are often at the partner site, which
   is why this is a text box and not a people picker). **Site Investigator**
   is the person *here* who answers for it.
3. **Review pathway**: **Ethics Pathway** is which route this takes:
   full committee, low or negligible risk review, or *quality assurance or
   evaluation - no ethics review*. That last one is not a shortcut; it is a
   decision somebody makes and this register records. **Participant
   Involvement** is a property of the study design and it helps justify the
   pathway.
4. **Ethics decision**: the committee's side. Status, their reference, the
   dates, and whether the approval carried **conditions**. If it did, the
   conditions box appears: paste the committee's **exact wording**.
   Paraphrase is how a condition quietly stops being met.
5. **Site authorisation**: our side. **Authorised By** names a **role**
   ("Chief Executive", "Director of Medical Services"), never a person: the
   individual changes and the delegation does not.
6. **Oversight and what is owed**: see below.

The form will not let you record a project as **site-authorised** unless
ethics is cleared, and it will not accept a submission, decision or
authorisation date in the future.

## Oversight, and the columns that stand in for lists

This register has no amendment rows and no report rows. Seven columns carry
that history instead, and they only work if you keep them:

- **Next Report Due**: when the next report is due. Your committee sets the
  date; some use the approval anniversary and some a fixed institutional
  date, so the register stores yours rather than guessing a cadence. Progress
  reports go to the committee **at least annually** and continued approval
  depends on them, so this is not a courtesy date.
- **Last Report Submitted**: when the last one actually went. Keep it, and
  an overdue Next Report Due becomes diagnosable: a due date in the past with
  a *later* submission behind it means somebody filed the report and did not
  roll the date, which is a completely different problem from a report nobody
  wrote.
- **Latest Amendment Reference / Status / Date**: the most recent amendment
  only. When the next one comes, these three are **overwritten**.
- **Amendment Count**: how many there have been in total. Bump it each time.
  Without it, a reader who sees "Amendment 3" cannot tell whether that is the
  only one or the fifth.
- **Governance Notes**: **the history, newest entry first, each entry dated
  and initialled.** This is where the amendments and reports that have no
  rows of their own survive. It is the most important box on the form and the
  easiest to skip.

Write it like this:

> today's date: Amendment 4 lodged, second recruitment site added (JS).
> 12 May 2026: Annual report filed and acknowledged (JS).

## Keeping it honest

- Record decisions **in the week they arrive**, not at report time.
- Both gates are recorded from the document, not from memory. An
  authorisation with no reference and no date has not been evidenced.
- When an approval lapses, set **Ethics Status** to *Expired*. Nothing
  computes it (the register cannot see today's date in a calculated column),
  so the readiness column stays wrong until a person moves it. This is what
  the monthly expiry sweep is for.
- Two amendments in flight at once? The columns hold one. Put the second in
  **Governance Notes** with its date, and reconcile when the first is decided.
- Never delete a project. Set the stage to **Completed** or **Discontinued**
  and it moves to **Archive** by itself.

## What NOT to do

- Don't paste report content, participant information or recruitment numbers
  into any box. The register indexes; the study file holds.
- Don't merge the two gates in your head. "It's approved" is not "it can
  start here", and the whole list is built to keep those apart.
- Don't paraphrase approval conditions.
- Don't fix a pink row by changing the stage. Tell research governance.
