# M365 adoption programme: programme team guide

Nine lists on one site, holding two layers of one programme. The standing
layer records who owes what permanently: `GOV_Activity`, the
stakeholders it names in `GOV_Stakeholder`, and the involvements that join
them in `GOV_Involvement`. The moving layer records what is
happening this fortnight: `GOV_Risk`, `GOV_Action`,
`GOV_Issue` and `GOV_Decision`. Between them sits
`GOV_ServiceRequest`, where every change only the shared services
provider can make is asked for, authorised, worked and closed.

The two layers meet at the workstream and nowhere else. Every risk,
action and service request names a workstream and will not save without
one. An issue may leave it blank, because the person who reports a
breakage is not always the person who knows which workstream owns it -
the **Needs triage** view catches the blank within a business day. An
activity or a decision may leave it blank too, because programme-wide
work exists and a false attribution is worse than a blank.

For step-by-step instructions - raising an issue, completing an action,
recording a decision, confirming an accountability, and the rest - see
`workflows/`, one short guide per task.

Seven of the nine lists carry a `Program` stem because the plain names
belong to other templates in this library. On screen they read *Program
Risk*, *Action*, *Activity* and so on.

## Which list does this go on?

| It is | List | Tell |
| --- | --- | --- |
| Might happen, might not | Risk | You can still change the odds |
| Is happening now | Issue | Somebody can describe it in the past tense |
| Somebody has to do it by a date | Action | It has a verb, one name and a date |
| The programme chose something | Decision | Someone will ask "why did we?" later |
| Only the provider can do it | Service Request | It needs tenant rights the health service does not hold |
| Somebody owes this permanently | Activity | It has no end date and it will still be true next year |
| Somebody must be asked or told about an activity | Involvement | You can write the sentence saying what input they give |
| A person, a role, a forum or an external body | Stakeholder | Something else needs to point at them by name |
| A stream of work | Workstream | Everything above hangs off it |

The distinction that costs the most when it is got wrong is the last
column of row five. An action nobody can start until the provider creates
a group is two records: a service request for the group, and an action
pointing at it through **Related Service Request**. Writing it as one
action leaves the programme unable to answer what it is waiting on.

A risk that materialises becomes an **issue**, and the risk is closed with
a closure note saying so. Do not delete the risk. It is the evidence that
the programme saw it coming.

**A person or a stakeholder?** A person column (Responsible, Accountable,
Decided By, Authorised By) names the individual who does or did something.
It is tied to an account, version history records who set it, and it is
never repointed afterwards. A row in Stakeholder names something
that outlives its holder: a position, a forum or an external body. That is
why involvements, decision routes and accountable forums point at
stakeholders rather than at people. On the stakeholder list itself, pick
**Role** when the involvement belongs to the position and should survive a
change of person, and **Individual** when it is this person specifically,
whatever they hold.

## The rhythm

Five cadences. The schema exists to serve them, and a list nobody reads on
a cadence is a list that rots.

| Cadence | Who | How long | What is read |
| --- | --- | --- | --- |
| Weekly, Monday, no meeting | Everyone named on a row | 10 minutes alone | Two personal views |
| Fortnightly | Programme owner and the five workstream leads | 45 minutes | The standing item below |
| Monthly | Steering group | 60 minutes | Risks in full, the provider queue, workstream phases |
| Quarterly | Register owner and governance | 90 minutes | The accountability register, in nine steps |
| Annually | Sponsor and governance | Half a day | Workstream set, stakeholders, escalation counts, adoption measures |

One thing that is not a cadence: **any material organisational change runs
the affected part of the quarterly review immediately**. A restructure, a
senior appointment or departure, a forum created or disbanded, a service
moved between teams, a new statutory or funding obligation, a change of
provider personnel, and any incident review that found nobody was clear
who owned something. This is the half of the review that gets skipped, and
skipping it is how the register stops describing the organisation.

### Monday, ten minutes, on your own

There is no reminder behind this read in phase one. It is a habit, and it
is the habit that makes every meeting below shorter.

1. `GOV_Action` opens on *My actions*: what you owe, soonest
   first. Overdue dates are red.
2. `GOV_Activity` opens on *My accountabilities*: what you answer
   for, whether you are Responsible or Accountable on it. A row washed
   gold is one somebody has said is wrong.

Both views follow whoever is signed in, so neither needs filtering. The
site home page links to them as *What do I owe?* and *What do I answer
for?* and those are the first two links on it.

### The 10-minute standing item

The fortnightly opens with two minutes in which every workstream lead
opens *My accountabilities* on the screen. Then this, in this order, and
the order is the point:

1. `GOV_Issue` -> *Open*, grouped by workstream. Facts before
   possibilities. Something already broken outranks something that might
   break, and Critical rows are washed across the whole row.
2. `GOV_ServiceRequest` -> *In progress*, then *Authorised, not yet
   picked up*. A row on the first with no **Assigned To**, or any row on
   the second, is a request the provider is not working. The commonest
   cause of a stalled workstream in this programme is something the health
   service does not control, so it is read early and the rest of the
   meeting goes on what can actually be moved.
3. `GOV_Action` -> *Overdue*, then *Open by person* opened at
   each person's group. Overdue first, so the exception is not buried in
   the whole list. This is the two minutes that make actions get done,
   because everybody knows the view is coming.
4. `GOV_Risk` -> *Review due*. Only the risks whose review date
   has arrived or passed. Re-rate, move the date forward, or close it. The
   full log is a monthly read, and walking every risk fortnightly is how a
   risk log becomes a ritual.
5. `GOV_Decision` -> *Awaiting decision*, then *Decision log*. The
   queue first: anything the meeting can answer, it answers now. Then the
   chair reads out anything decided since last time, in thirty seconds.
   Anything the meeting has just decided is typed in **before the meeting
   ends**. That last discipline is the one most likely to lapse and the one
   that costs most when it does. Read *Stalled proposals* too, whenever it
   has rows: those have missed two cycles already.

Nothing else needs writing up. For most programme meetings these five
reads replace long-form minutes.

### Monthly, at the steering group

`GOV_Workstream` -> *The programme* in sequence, which is the whole
programme on one screen. Then `GOV_Risk` -> *Open*, worst score
first, which is the only cadence that reads the full risk log. Then
*Closed this quarter*, where every row should carry a closure note and
nothing checks that but a person. Then `GOV_ServiceRequest` ->
*Escalated* and *Needed soon or overdue*. Then the graduation check: a
risk whose consequence has outgrown the programme is raised on the
organisational risk register, and the programme row is then closed with a
closure note naming where it went. That is a copy rather than a move, so
the programme keeps its evidence that it spotted the risk and the two
registers never hold two half-maintained copies of one rating.

### Quarterly, the accountability review

Nine steps, and the per-row confirmation cadence (six, twelve or
twenty-four months by criticality) is the floor rather than the schedule.

1. `GOV_Activity` -> *Confirmation due*. Re-read each row,
   correct it, then confirm it.
2. *Needs review*. The rows somebody has said are wrong. They should not
   survive two consecutive reviews.
3. *By workstream*. Each lead reads their own accountabilities as a block.
4. *Workstream leads*. Exactly one current lead per workstream, checked
   against `GOV_Workstream`'s own row count, because a workstream with
   no lead has no group heading and is invisible in a grouped view.
5. *Decisions and approvals*, grouped by forum. Every non-Task row should
   have an escalation route naming somebody reachable, and the forum it
   groups under should still exist.
6. `GOV_Involvement` -> *Consultation load*. One stakeholder consulted
   on everything is the failure this view exists to reveal.
7. `GOV_Stakeholder` -> *Active stakeholders*, against the org chart. An
   external stakeholder with no **External Contact Details**, and any other
   non-forum stakeholder with no **Contact**, is a name nobody can act on.
8. Look for the activities that are not there. No view can show an absent
   row, so the walk has three axes: each workstream, the programme-wide
   rows whose workstream is blank, and the work that happens between the
   two organisations, which is the axis most likely to fail because it is
   nobody's default responsibility.
9. Version history on every row changed since the last review, and
   `GOV Accountability Maintainers` membership against the people
   currently named Responsible and Accountable.

### Annually

The workstream set, the stakeholder vocabulary, the count of service requests
that reached escalation levels 3 and 4, the minutes spent on closed
requests (the total under *Closed*), and the five adoption measures in
`measures-register` against their baselines. The escalation count and the
effort total are the health service's evidence at the shared-service
agreement review, which is the strategic reason the service request list
exists.

## Raising a risk

**A risk has not happened yet.** If it is already happening it is an
issue, and putting it on the risk log buys the programme nothing but a
rating.

1. `GOV_Risk` -> **New**. Title it as an uncertain event: "The
   provider does not create the pilot group before the pilot starts", not
   "Pilot group".
2. **Workstream** is required. It is what lets a lead read their own risks
   rather than the whole programme log.
3. *Describe it*: cause, event, consequence in **Detail**. What could
   trigger it, and what happens to the programme if it does.
4. *Assess it*: **Likelihood** and **Consequence** as things stand today,
   with whatever is already in place. **Residual Risk Rating** and **Risk
   Score** calculate themselves and there is nowhere to type over them. If
   you disagree with the answer, the argument is about the two inputs.
5. *Own it*: one **Risk Owner**, never a team, and a **Risk Response**.
   Tolerate is always for a set period and belongs in the decision log.
6. *Review it*: a **Review Date** set from how fast the risk could move,
   not from a calendar habit. **Closure Note** appears once you set the
   status to Closed. Nothing refuses a save without it, which is exactly
   why it is read at the steering group.

## Writing an action people do

`GOV_Action` -> **New**. A verb for a title, one **Assigned To**,
one **Workstream**, a real **Due Date**. All three are required and the
form will not let you skip any of them. "The team" and "ASAP" are how
actions quietly die.

- **Workstream Phase** shows beside the workstream, read-only. If it says
  Closed, the action is filed against a workstream that has finished. The
  list cannot prevent that, so it shows it to you instead.
- **Related Risk** is optional and usually blank. Fill it in when the
  action exists *because* of a risk. The picker only offers risks that are
  still Open; a closed risk cannot be the reason for new work.
- **Related Service Request** is the other optional link, and it is the
  one this programme needs most. Fill it in when the action cannot finish
  until the provider does something. Without it the request ends up
  described in **Notes**, where nothing can read it.
- Done: set Status **Done**. **Completed Date** appears and the form will
  not save without it. It cannot be in the future.
- Cannot make the date? Move it and say why in **Notes**. A moved date
  with a reason beats a silently overdue action.
- An action that no longer makes sense goes to **Dropped** with a note.
  Nothing refuses that save, deliberately. Dropping honestly is better
  than leaving it Open forever.

## Raising an issue

**An issue is a fact.** "The pilot group has not been created" is an
issue. "The pilot group might not be created in time" is a risk. Write
what is happening, since when, and what it is costing the programme, in
**Detail**.

- **Severity** is how much it is hurting the programme right now, not how
  much it might. Re-set it as the answer changes.
- **Owner** is one person who drives it to a resolution, and it is not
  always the person who raised it.
- **Related Risk** is the honest one to fill in. An issue that was on the
  risk log first is the register working, and leaving the link blank is
  how a programme loses the evidence that it saw this coming.
- **Resolved** means it has stopped happening. **Closed** means somebody
  has confirmed that. Both need a **Resolved Date**, which appears as soon
  as you pick either, and the form will not save without it.
- Anything Major or Critical is on *Severe and open* the moment you save
  it. Do not wait for the fortnightly to mention it.

Many issues in this programme are a service request that has sat with the
provider. Raise both, and link the action to the request.

## Asking for a decision, and recording one

`GOV_Decision` holds two things: proposals nobody has answered yet,
and decisions that were made. **Status** is what separates them, and the
list opens on *Awaiting decision* rather than on the log.

State the row as a decision either way: "We will run the telephony pilot
with one directorate only", not "Discussed telephony pilot scope". A
proposal written as a topic cannot be approved, because nobody can tell what
approving it would mean.

**To put something to a forum**, create the row before the meeting.
**Status** stays *Proposed*, **Raised Date** fills with today, and
**Resolution Sought** is what you are asking the forum to decide. Leave
**Decision Date** blank; the form will not accept a date the forum has not
reached yet. Set **Activity** where the proposal belongs to a standing
activity, so the route it should follow is on the row. Leave it blank when
there is no standing activity, which is the ordinary case.

**To record what was decided**, open the same row afterwards. Set **Status**,
fill **Decision Date**, and put what was actually decided in **Decision
Outcome**, which is separate from Resolution Sought so an amendment does not
overwrite what was asked. **Decided By Forum** is the forum that decided.
**Recommended By Forum** is the committee that recommended first, where one
did. **Decided By** is one person, for a call one person made.

The five outcomes:

- **Approved** and **Rejected** mean the forum decided.
- **Ratified** means somebody decided under delegation and the forum
  validated it afterwards. Use it rather than backdating an approval.
- **Noted** means the forum noted the paper and no decision was required.
- **Withdrawn** means it was taken off the table before anybody decided.

Anything but *Proposed* and *Withdrawn* needs a Decision Date, and the form
says so on save.

A decision recorded after the fact is still worth typing. Set Status,
Decision Date and Raised Date to when it was raised, and leave Resolution
Sought blank; nothing requires the proposal half.

**Detail** carries the options considered, why this one, and who disagreed.
That last part is what stops the decision being reopened in six months by
somebody who was not there.

Nobody on the site can delete a decision or a proposal, deliberately. The
log's whole value is that it survives, and *Withdrawn* is how a proposal
ends. Superseding a decision is a new row that references the old one.

Pickers on other lists only offer decisions that were **Approved** or
**Ratified**. A proposal nobody has answered cannot be cited as authority
for an action, a risk tolerance or a service request, which is the point.

## Raising a service request

**This list is the request surface.** A change only the provider can make
is asked for here, authorised here, worked here and closed here, on one
row. The health service owns the first half of the row: what was asked
for, why, who authorised it internally and when it is needed. The
provider's handler owns the second: who holds it, where it is, and the
minutes spent on it.

1. `GOV_ServiceRequest` -> **New**. **Title**, **Workstream**, **Request
   Type**, **Justification**, **Requested By**, **Internal Accountable**
   and **Needed By** are all required. **Justification** is the only
   narrative field on the list and it is the brief the handler works from.
2. You will not see **Status**, **Assigned To** or **Minutes Spent**. They
   are hidden from the New form, and Status defaults to Drafted, because a
   submitter who can pick their own status can authorise their own request.
3. Governance authorises it: **Authorised By** and **Authorised Date**,
   which appear only once the record exists and only in the states they
   are owed in. Governance may name the handler in **Assigned To** at the
   same time, or leave that to the provider.
4. A handler picks it up: **Assigned To** to themselves and Status to In
   progress. From here the handler owns the row. If they need something
   from the health service before they can continue, Status goes to
   Waiting on requester, and the row stays open and visible until the
   answer arrives and the handler moves it back.
5. The handler closes it: Status to Closed, with **Minutes Spent** as the
   running total of whole minutes spent on it. The form will not save a
   closed request without that number, and zero is an answer. Closed means
   the provider has finished; a request the programme no longer wants ends
   as Withdrawn instead, set by governance.

**You cannot edit your own request after saving it.** Site members hold
add and read on this list and nothing else. That is deliberate: a
correction to an authorisation record should go through the people who
authorised it, and only governance and the handlers can move a row. Ask
governance.

Escalation is a governance act on a record that already exists, so the
four escalation fields are off the New form entirely. **Escalation Level**
records the highest level reached rather than a history; the sequence is
in version history. Levels 1 and 2 are operational chasing. Levels 3 and 4
are contractual, they move at the speed of an agreement rather than of a
programme, and they are the two that get counted at the annual review.

## Who leads a workstream

`GOV_Workstream` carries no person column. Not a lead, not a sponsor,
not an owner. Who leads a workstream is answered by an activity row
carrying **Activity Role**, which takes *Workstream lead*, *Workstream
deputy* or *Program owner* and is blank on every ordinary row.

The reason is that the accountability register is the one place with a
confirmation cadence, an escalation route and a review status behind it. A
lead column on the workstream would have none of those and would go stale
the first time a lead changed.

To look one up, open `GOV_Activity` -> *Workstream leads*, which
groups the current lead rows by workstream. Two rows under one heading
means two leads, and a workstream missing from the view entirely means it
has none. Neither can be prevented at save, because a SharePoint
validation formula reads only the row being saved and cannot count rows
across a list.

A row carrying any **Activity Role** must name an **Escalation Route**,
alongside the existing rules for a Decision and for anything Statutory.
The field appears on the form the moment you make the row one that needs
one. A standing position with no tie-break is the position that stalls at
the worst moment, and "escalate as required" is not a route: it names
nobody and resolves nothing at 4pm on a Friday.

## Correcting and confirming your own row

If you are named Responsible or Accountable on an activity, you may
correct that row and confirm it yourself. Version history records who
changed what, and the quarterly review reads the history of every row
changed since the last one.

That is the mechanism rather than a policy. SharePoint cannot express
"edit only your own row" against a person column, so edit rights come from
membership of `GOV Accountability Maintainers`, which holds everyone
currently named Responsible or Accountable, plus governance, and is
reconciled at the quarterly review. Nobody in it can delete a row or prune
its history, so the worst a disagreement can produce is a row that
changed, visibly, twice.

**Confirming is not the same as editing.** Re-read the row, check it is
still true, then set **Last Confirmed** to today and **Confirmed By** to
yourself. That pair of edits is the only thing that moves **Confirmation
Due** forward, and it is what tells everyone else a human has looked at
the row rather than merely touched it. **Last Confirmed** does not appear
when you create an activity, because it fills itself with today's date. It
will not accept a future date.

**If a row is wrong, set Review Status to *Needs review* and save.** That
is all it takes, and it is the most useful thing you can do in this
register. You do not need to know the right answer first. The row washes
gold in *My accountabilities* and *By workstream*, where everybody sees
it. *Retired* is different: it is for an activity that genuinely stopped
happening, and it keeps the history while dropping the row out of every
working view.

Confirm sooner than the cadence whenever something material changes. The
due date is a ceiling, not a target.

## The healthcare boundary

**Nothing patient-identifiable belongs in any of these lists, in any
field, or in any attachment. Ever.** No names, no UR numbers, no dates of
birth, no clinical detail, and nothing that identifies a patient in
combination with anything else on the row.

Nothing checks this. Multi-line fields cannot be validation operands, so
the sentence on three of the forms is a prompt and not a control. What
backs it up is that there are few places to type prose at all
(**Justification** on a service request, **Detail** and **Resolution** on
an issue, **Detail** and the **Closure Note** on a risk, **Notes** on an
action, **Detail** on an activity and on a decision), that attachments
are turned off on all nine lists as a go-live
step, and that the programme owner samples the narrative fields every
quarter and redacts what should not be there.

The realistic leak is not prose. It is a screenshot proving a migration
bug, showing a mailbox with patient names in it. That is what the
attachment setting is for. If you find a list offering you an attachment,
tell the site owner rather than using it, because the setting is manual
and a redeploy does not reassert it.

## The views you will actually use

| View | List | What it is for |
| --- | --- | --- |
| *My actions* | Action | What you owe, soonest first. The default |
| *Overdue* | Action | Read first at the fortnightly, so it is not buried |
| *Open by person* | Action | Grouped by owner, opened at each person's group |
| *My accountabilities* | Activity | What you are accountable for. The default, and gold means somebody has said it is wrong |
| *Confirmation due* | Activity | Falling due within thirty days, or already past |
| *Workstream leads* | Activity | Who leads what, grouped by workstream. Exactly one each |
| *Consultation load* | Involvement | Consulted rows grouped by stakeholder. A long list is the overload failure showing itself |
| *In progress* | Service Request | What the provider holds, including anything handed back. The default |
| *Authorised, not yet picked up* | Service Request | Authorised here but no handler has taken it, so the provider is not working it |
| *My assigned requests* | Service Request | The handler's own queue, soonest needed first |
| *Closed* | Service Request | The effort record, with the minutes spent totalled |
| *Needed soon or overdue* | Service Request | Within fourteen days of the needed-by date |
| *Open* | Issue | What is broken, grouped by workstream. The default |
| *Severe and open* | Issue | Major and Critical only |
| *Open* | Risk | The full log, worst score first. Read monthly |
| *Review due* | Risk | Only the risks actually due. Read fortnightly |
| *The programme* | Workstream | Phase and dates for every stream, in sequence |
| *Decision log* | Decision | Everything decided, newest first |

## What not to do

- Do not keep a second record of a request anywhere else. The row in
  `GOV_ServiceRequest` is the request, from draft to closure, and a copy
  maintained by hand beside it disagrees with it inside a month.
- Do not leave a request Drafted and assume the provider has it. Nothing
  reaches a handler until governance authorises it and somebody picks it
  up, and *Authorised, not yet picked up* is the only thing that catches
  the gap.
- Do not describe a request in an action's **Notes**. **Related Service
  Request** is the field for it, and it is the only one anything can read.
- Do not put a risk on the log with a review date you do not mean. An
  unreviewed risk log is a document, not a control.
- Do not invent a **Related Risk** to fill the column in. Most actions are
  ordinary programme work and the link is blank on purpose.
- Do not assign actions to people who were not in the meeting without
  telling them.
- Do not reword a decision after the fact. Record a superseding decision
  and reference the old one.
- Do not overwrite **Resolution Sought** with what was decided. The two
  columns are separate so that an amended decision still shows what was
  asked.
- Do not leave a proposal *Proposed* once the forum has answered it. A
  queue nobody clears stops being read, and *Stalled proposals* cannot tell
  a neglected row from a finished one nobody updated.
- Do not leave an accountability row you know is wrong. Setting *Needs
  review* takes ten seconds and is the supported path.
- Do not delete a stakeholder, a decision or an activity. Retire them: **Review
  Status** *Retired* on an activity, **Status** *Inactive* on a stakeholder.
  Deleting a stakeholder orphans every activity and involvement pointing at it,
  and the children survive pointing at nothing, which reads as a blank
  cell rather than as an error.
- Do not attach anything, and do not paste a screenshot into a narrative
  field.
