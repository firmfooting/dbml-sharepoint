# RAID log: project team guide

Four lists, one habit. R and I are what might go wrong and what already
has; A is what somebody is doing about it; D is why the project chose what
it chose. The lists are worth keeping only if they are read together, so
start with the meeting.

## The 10-minute standing item (project manager)

Every project meeting, in this order:

1. **Project Issue** -> *Open*. Oldest first, because the issue nobody has
   mentioned for three weeks is the one the project has stopped noticing.
   Anything Critical is washed across the whole row.
2. **Project Action** -> *Open by person*, opened at each person's group.
   Overdue dates are red. This is the two minutes that make actions get
   done, because everybody knows the view is coming.
3. **Project Risk** -> *Review due*. Only the risks whose review date has
   arrived or passed. Re-rate, move the date forward, or close it.
4. **Project Decision** -> click **New** for anything the meeting just decided.

Nothing else needs writing up. For most project meetings these four lists
*replace* long-form minutes.

## Raising a risk

**A risk has not happened yet.** If it is already happening it is an issue,
and putting it on the risk log buys the project nothing but a rating.

1. **RAID_ProjectRisk** -> **New**. Title it as an uncertain event:
   "Supplier misses the integration milestone", not "Supplier" and not
   "Integration".
2. *Describe the risk*: cause, event, consequence in **Detail**. What could
   trigger it, and what happens to the project if it does.
3. *Assess the risk*: pick **Likelihood** and **Consequence** as things
   stand today, with whatever is already in place. The rating and the score
   calculate themselves and there is nowhere to type over them. If you
   disagree with the answer, the argument is about the two inputs.
4. *Response and owner*: what the project is doing about it, and **one**
   owner. Never a team.
5. *Review and closure*: a **Review Date**. Set it from how fast the risk
   could move, not from a calendar habit: a risk about next week's cutover
   is reviewed next week.

## Writing an action people actually do

**RAID_ProjectAction** -> **New**. A verb for a title, **one** named owner,
a real date. Both owner and date are required and the form will not let you
skip either, which is the point. "The team" and "ASAP" are how actions
quietly die.

**Related Risk** is optional and usually blank. Fill it in when the action
exists *because* of a risk: that is what makes the risk's response
something you can point at rather than a word in a column.

- Your queue is ***My actions***. It follows whoever is signed in, so it is
  your list without you filtering anything.
- Done: set Status **Done**. The **Completed Date** field appears when you
  do, and the form will not save without it. An action finished on a date
  nobody can name is still In progress.
- Cannot deliver by the due date? Change the date and say why in Notes. A
  moved date with a reason beats a silently overdue action. Until you do,
  the date is red with a warning icon everywhere it appears.
- An action that no longer makes sense -> **Dropped** with a note. Nothing
  refuses that save, deliberately: dropping honestly is already better than
  leaving it Open forever.

## Raising an issue

**An issue is a fact.** "The test environment has been unavailable since
Tuesday" is an issue. "The test environment might be unstable" is a risk.
Write it as the thing that is happening, with **since when** and **what it
is costing the project** in Detail.

- **Severity** is how much it is hurting the project *right now*, not how
  much it might. Re-set it as the answer changes; nothing here is a
  once-only field.
- **Owner** is one person who drives it to a resolution. It is not always
  the person who raised it.
- **Related Risk** is the honest one to fill in. An issue that was on the
  risk log first is the register working; leaving the link blank when it
  was there is how a project quietly loses the evidence that it saw this
  coming.
- **Resolved** means it has stopped happening. **Closed** means somebody
  has confirmed that. Both need a **Resolved Date**, which appears as soon
  as you pick either, and the form will not save without it.

## Recording a decision

**RAID_ProjectDecision** -> **New**, at the meeting or straight after.
State it *as a decision*: "We will drop reporting from phase one", not
"Discussed reporting scope".

In **Detail**, the options considered, why this one, and who disagreed.
That last part is what stops the decision being reopened in six months by
somebody who was not there. **Decided By** is one person; leave it blank
when a board or a group decided, and name the group in Detail.

## Which list does this go on?

| It is | List | Tell |
| --- | --- | --- |
| Might happen, might not | Risk | You can still change the odds |
| Is happening now | Issue | Somebody can describe it in the past tense |
| Somebody has to do it | Action | It has a verb and a date |
| We chose something | Decision | Someone will ask "why did we?" later |

A risk that materialises becomes an **issue**, and the risk gets closed
with a closure note saying so. Do not delete the risk: it is the evidence
that the project saw it coming.

## What NOT to do

- Don't put a risk on the log with no review date you actually mean. An
  unreviewed risk log is a document, not a control.
- Don't assign actions to people who were not in the meeting without
  telling them.
- Don't reword a decision after the fact. Record a superseding decision
  and reference the old one.
- Don't delete anything. Closed risks, dropped actions and resolved issues
  are the project's memory, and they are the whole content of a lessons
  session at the end.
