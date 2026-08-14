# RACI matrix: staff guide

*Maintained by RACI Matrix Maintainers; readable by everyone.*

This register answers one question: **for this piece of work, who does it,
who answers for it, who has to be asked, and who has to be told?** It is
worth reading the whole of this guide before you write your first row.
The method is simple and the ways it goes wrong are not obvious.

## The four letters, on the row in front of you

Open any activity. Four things are recorded about it, and they are not
four flavours of "involved".

**Responsible: who does the work.** One named person, in the
`Responsible` column. Not a team, not a department: the person whose
week the work actually lands in. If you cannot say a name, the activity
is not yet described well enough to be in the register.

**Accountable: who answers for the outcome.** One named person, in the
`Accountable` column. This is the person who is asked "why did this not
happen?", and who cannot answer by pointing sideways. Often, and quite
properly, the same person as Responsible on small work. Never two people.

**Consulted: who must be asked before it proceeds.** These are not on
the activity at all; each one is a row in **Involvement** with
`Involvement` set to *Consulted*. Consulted means their input is required
*before* the thing happens, and that they can hold it up. That is a real
power, so it is given deliberately rather than by default.

**Informed: who is told.** The same list, `Involvement` set to
*Informed*. Told afterwards, or told as it goes; cannot hold it up.
Being Informed is not a lesser insult, it is a different relationship.

The split between the two lists is doing work. Responsible and
Accountable are single columns on the activity **because there is exactly
one of each**. Consulted and Informed are rows in a second list **because
there can be any number**, and because every one of them has to say
something more than a name.

### Where the forum fits

`AccountableForum` names the committee or meeting an accountability is
exercised through: the Clinical Governance Committee, the executive
team, a board sub-committee. It is optional and it does not replace the
Accountable person. A committee cannot be performance-managed, cannot be
asked in a corridor, and disperses responsibility exactly when you need
it concentrated. The person still answers; the forum is where they answer
*to*.

## Task, Approval, Decision, and why the register asks

`ActivityKind` has three values, and R and A mean subtly different things
in each. Getting this wrong is how a register that looks complete gives
people the wrong expectation of each other.

| Kind | Responsible | Accountable |
| --- | --- | --- |
| **Task** | Does the work | Owns the outcome |
| **Approval** | Prepares the thing and puts it up | Signs it |
| **Decision** | Runs the process: options, analysis, consultation | Makes the call |

A Task is the ordinary case: publish the roster, verify the restore,
lodge the return. An Approval has a prepare/sign shape, and the value of
recording it is that everyone knows which end they are on. A Decision is
the one to think hardest about, for the reason below.

`EscalationRoute` is required on any Decision and on anything Statutory:
say where it goes when Responsible and Accountable cannot agree. "The
Executive Director, then the Finance and Audit Committee at its next
sitting" is a route. "Escalate as required" is not. It names nobody and
resolves nothing at 4pm on a Friday.

The field only appears on the form in those two cases (when the kind is
Approval or Decision, or when the criticality is Statutory) rather than
sitting blank on every routine task. If it is on your screen, the register
will not let you save without it. If it appears while you are part way
through a row, it is because you just made the activity one that needs
one.

## What this register is not: a way to decide

**RACI governs execution. It has no decider.** Accountable means "owns
the outcome", not "makes the call", and no letter in RACI means "chooses".
That is not a gap somebody forgot to fill; it is what RACI is.

The practical consequence is worth stating flatly, because it is the
failure that wastes the most time: **a group trying to use a RACI to
*make* a decision deadlocks.** Everybody is consulted, nobody is
empowered, and the meeting ends by scheduling another meeting. People
then blame the matrix, when the matrix was never designed to do it.

If what you have in front of you is genuinely a decision (options on the
table, someone who must choose, people whose agreement is needed, someone
who can veto), then you want a decision-rights method built for it. DACI
(Driver, Approver, Contributors, Informed) and RAPID (Recommend, Agree,
Perform, Input, Decide) both name a decider explicitly, which is exactly
what RACI declines to do. **Use one of those, and record the *outcome*
here** as the activity it becomes.

The `Decision` kind in this register is for a decision that recurs and
has a settled shape ("approve a new supplier above the executive
threshold") where naming who runs the process and who makes the call is
useful standing information. It is not a substitute for a decision-making
method on a one-off strategic choice, and the register cannot tell the
difference. Only you can.

## The five ways a RACI fails

Every one of these is documented, common, and has killed a matrix
somebody spent weeks on. Three of them this template makes structurally
impossible. Two it can only make visible, and you are the control.

| Failure | What it looks like | Here |
| --- | --- | --- |
| **Two Accountables** | Two names on one row, each assuming the other is watching | **Impossible**: `Accountable` takes one person |
| **A team as Responsible** | "Engineering team" holds R; nobody individually feels it | **Impossible**: `Responsible` is a person column |
| **Anonymous Consulted** | A column of names with no reason attached | **Impossible**: every involvement is a row whose Title must state the input |
| **The laminated artefact** | Built over weeks, hung on a wall, dead in six months | **Visible, not prevented**: the confirmation cadence and the *Needs review* wash |
| **Used to decide** | The matrix is asked to make a call it has no decider for | **Named, not prevented**: the kinds teach the difference; nothing stops misuse |

**Two Accountables is the most-cited killer**, and it fails in a
particular way: it does not look like a failure. The row reads as
thorough. Then the moment arrives when somebody has to answer, and both
named people look at each other, each having assumed the other was
carrying it. If your instinct is that a row needs two Accountables, the
row is describing two activities. Split it.

**A team as Responsible** is clarity in appearance and none in substance.
"The finance team" does the reconciliation is a sentence nobody in the
finance team hears as being about them. This register will not accept it,
which occasionally feels obstructive on a genuinely shared task. The
answer there is a named person who is responsible for it *happening*,
with the rest of the team's involvement recorded as involvements.

**Consulted overload** is the failure the *Consultation load* view exists
to catch. It arrives politely: nobody wants to leave anyone out, so
everyone becomes C on everything, and the column stops being a functional
input list and becomes a political protection list. The test is the one
the involvement Title forces on you: **can you write the sentence that
says what input this party gives?** "Pricing tolerance and contract
terms" is an input. "Because they'll want to know" is not. That party is
Informed, or nothing at all. A party you cannot write the sentence for is
not Consulted, whatever the politics say.

**The laminated artefact** is the quiet one. A matrix is not a document
you finish, it is a description of how the organisation currently works,
and organisations change every week. That is what `LastConfirmed`,
`ConfirmationDue` and the *Confirmation due* view are for: they are the
mechanism that stops this becoming a wall poster describing a company
that no longer exists.

## The objection you should hear from somebody, and it is fair

A RACI applied rigidly is a very good instrument for a blame culture.
Each letter becomes a way to point at somebody: *you were R, so this is
on you*; *I was only C, so don't look at me*. Hard boundaries around
boxes wall people off from helping each other, and "not my row" is a
sentence no team benefits from hearing.

That risk is real, and it is not fixed by a column. It is fixed by how
the register is used, which comes down to two habits:

- **Read it forwards, not backwards.** The matrix is for knowing who to
  go to before work starts. Using it after something goes wrong, to
  establish whose fault it was, teaches everyone to negotiate their
  letters defensively, and a register whose rows are negotiated
  defensively is worthless as a description of how work happens.
- **Accountability is not blame.** Being Accountable means you answer for
  the outcome, including by getting help early. The point of naming one
  person is that somebody is *watching*, not that somebody is *liable*.

If your organisation cannot hold that distinction, this register will
make an existing problem more legible rather than causing a new one. That
is worth knowing before you deploy it, not after.

## Writing a good row

**Activities are verb phrases.** "Approve a new supplier above the
executive threshold", "Publish the fortnightly staff roster", "Lodge the
annual regulatory return". Not "Supplier approvals" and not "Rostering".
A noun is a topic, and a topic has no Responsible.

**Use `Detail` to write the boundary.** What this activity covers and,
just as usefully, what it does not. "The annual return covering the full
financial year; the quarterly data submissions are a separate activity."
That sentence is what stops somebody claiming a neighbouring piece of
work was included in a row they never read.

**`Criticality` is about consequence, not effort.** *Statutory* means law,
a licence or a funding agreement requires it. *High* is serious harm to
the organisation if it fails. *Routine* is everything else. It is not a
measure of how hard the work is, and it drives how often the row must be
re-confirmed: six months, twelve, twenty-four.

**Then add the involvements.** One row per party, in the Involvement
list. Title states the input. `Channel` says how it actually happens: a
standing agenda item, a meeting, an email, a report, ad hoc. An
involvement with no realistic channel is a promise nobody keeps. If the
only way this consultation happens is somebody remembering, say so in
`Notes` and expect it to fail.

## Saying "this row is wrong"

**Set `ReviewStatus` to *Needs review*, immediately, and save.** That is
all it takes, and it is the single most useful thing you can do in this
register.

You do not need to know what the right answer is. You do not need to wait
for the review. You do not need to have worked out who it should be
instead. The row will wash gold in the **Current** view, which everybody
sees, and the maintainers will get to it.

A row marked *Needs review* is more trustworthy than a row that looks
correct and is not, because the first one is honest about its state.
The alternative, leaving a wrong row alone because flagging it feels
like making a fuss, is exactly how a register becomes something people
quietly stop believing, and after that it does not matter what is in it.

If you are not in RACI Matrix Maintainers you cannot set it yourself.
Tell a maintainer; that is a thirty-second conversation, and it is the
supported path.

*Retired* is different: it is for an activity that genuinely stopped
happening. Retiring keeps the history (who used to do this, and that it
ended) while dropping the row out of every working view and blanking its
`ConfirmationDue`, because nobody needs to re-confirm work nobody does.

## Confirming a row

Confirming is not the same as editing. **Re-read the row, check it is
still true, then set `LastConfirmed` to today and `ConfirmedBy` to
yourself.** That pair of edits is the only thing that moves
`ConfirmationDue` forward, and it is what tells everyone else the row has
been looked at by a human rather than merely touched.

`ConfirmationDue` is calculated and cannot be typed. It is
`LastConfirmed` plus the interval `Criticality` sets, and it goes blank on
a Retired row. Past due, the cell turns red with a warning icon.

You will not see `LastConfirmed` when creating an activity: it fills
itself with today's date, which is the baseline every later cadence counts
from. It appears once the activity exists, which is the only point at
which moving it means anything. It will not accept a future date: a year
typed wrong pushes the confirmation out by a year and silently drops the
row off *Confirmation due*, where nobody would notice its absence.

**Confirm sooner than the cadence whenever something material changes.**
A restructure, a resignation, a new statutory obligation, a service
moving between teams: the due date is a ceiling, not a target.

## The views you will actually use

| View | List | What it is for |
| --- | --- | --- |
| **Current** | Activity | The register, minus retired rows, soonest due first. Gold rows need review |
| **My accountabilities** | Activity | Everything you personally answer for. Read this one first |
| **Confirmation due** | Activity | Falling due in the next 30 days, or already past |
| **Decisions and approvals** | Activity | The non-Task rows, grouped by the forum they run through: the governance pack |
| **By activity** | Involvement | One group per activity: its consulted and informed list. This is the matrix as it is usually drawn |
| **By party** | Involvement | Everything one person, role or forum is involved in |
| **Consultation load** | Involvement | Consulted rows only, grouped by party. Somebody with a long list here is the overload failure showing itself |
| **Active parties** | Party | The vocabulary, minus anyone retired |

> **You need to be in the RACI Matrix Maintainers group to edit anything
> here.** Being named in `Responsible` or `Accountable` does not grant
> access. Those columns record accountability, not permission. Everyone
> else on the site has read access, which is deliberate: anybody should be
> able to look up who is accountable for something without asking. If you
> have been made Accountable for a row and the form opens read-only, ask
> your site owner about RACI Matrix Maintainers; you are not doing
> anything wrong.
