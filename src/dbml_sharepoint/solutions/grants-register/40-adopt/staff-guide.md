# Grants register: guide

## The views, both lists

They deploy with the lists. Nothing here is something you build, and you
shouldn't rename them, because a redeploy puts the declared name back.

### GR_Submission

| View | What it shows |
| --- | --- |
| **Pipeline** | The default. Bids in preparation or with the funder, closing soonest first. |
| **Live grants** | Successful bids whose funded activity has not ended, with the agreement link. |
| **By funder** | Everything, grouped by funder (the relationship file). |
| **Lost bids** | Unsuccessful and withdrawn bids, with the debrief. |

### GR_Acquittal

| View | What it shows |
| --- | --- |
| **Open obligations** | The default. Everything not yet accepted by the funder, due soonest first. Overdue rows are tinted. |
| **Due 90 days** | The sweep view: upcoming and in-preparation obligations due inside a *rolling* ninety days. |
| **Overdue** | Exactly what it says, with the Notes column where the recovery date goes. |
| **By grant** | Obligations grouped by the grant they belong to. Expand a grant to see everything it owes. |
| **Filed** | Submitted and accepted obligations, most recent first, with the evidence link. Funders audit years later. |

## Anyone considering a bid

Check the register first: **By funder** shows whether we already have a
relationship (or a live application) with that funder. Two uncoordinated
approaches to one funder is the classic small-organisation own-goal. Then
talk to the grants coordinators **before** writing; the bid/no-bid
questions in governance take ten minutes and save wasted weekends.

## Coordinators: the pipeline

1. A bid worth pursuing → **GR_Submission** row at **In preparation**:
   funder, round deadline, amount, a named **Grant owner** (the person who
   will own delivery if it wins, decided *before* submission, not after).
   The post-award fields are not even on the form yet.
2. Lodged → **Submitted**. **Submitted date** appears the moment you
   change the outcome, and the list will not let you save without it.
3. Outcome:
   - **Successful** → **Amount awarded**, **Agreement URL** and **Project
     end date** appear. The list requires the amount, from the agreement
     rather than the announcement; it cannot check the link, so that one
     is on you. Then do the sign-then-load habit below *the same week*.
   - **Unsuccessful** → the ten-minute debrief goes in **Project
     summary**: feedback received, what we'd change. Nothing enforces
     this (a rich-text field cannot be checked at save) and the *Lost
     bids* view shows the column so an empty one is obvious. Lost bids are
     purchased market intelligence; unrecorded, they're just lost.
   - **Withdrawn** → for a bid stopped before lodgement. No submitted date
     is required, because there was no submission.

## The sign-then-load habit (the register's reason to exist)

The week a funding agreement is signed, read it with a highlighter and
create **one Acquittal row per obligation**: every progress report,
financial acquittal, audit requirement and evaluation: title, due date,
where it goes. Fifteen minutes now converts every future deadline from a
memory into a view.

## The monthly obligations sweep (coordinators, 10 minutes)

1. **Due 90 days**: each obligation has someone preparing it (nudge the
   grant owner; move to **In preparation**).
2. **Submitted** → **Submitted date** and **Evidence URL** appear on the
   form. The list requires the date. It cannot check the link, and an
   acquittal nobody can produce a copy of is the same as one that was
   never sent, so fill it in anyway. Then chase the funder's acceptance
   where that's a thing (**Accepted by funder**). A submitted obligation
   stays amber until they confirm, because it is still waiting on
   someone.
3. Anything past due → **Overdue**. The row turns a tinted red in **Open
   obligations** (the only row-level signal on either list, reserved for
   this one state) and the escalation in governance fires. An overdue
   acquittal is a funder-relationship incident, not an admin slip.
