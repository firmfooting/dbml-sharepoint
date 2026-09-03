# Programme governance: how the family is governed

Ten lists enforce what SharePoint can enforce, and `20-configure/mapping.yaml`
holds every one of those rules. This document holds the rest: the obligations
the platform cannot express, who performs them and when, and what is safe to
change once the programme is running.

## Ownership

| Role | Held by | Accountable for |
| --- | --- | --- |
| Programme owner | *(e.g. the transformation or digital programme manager)* | That the cadences below happen; the quarterly sampling of narrative fields; this document |
| Register owner | *(e.g. the governance lead)* | That the accountability register describes the programme as it is today; the quarterly review and its version-history read |
| Workstream lead | The `GOV_Activity` row whose `ActivityRole` is `Workstream lead` | That workstream's risks, actions, issues and service requests, and its block of the register |
| Accountable, per activity | The `Accountable` column | That the activity happens, and that the row describing it stays true |
| Responsible, per activity | The `Responsible` column | Doing the work, and saying when the row no longer matches reality |
| Risk, action and issue owners | `RiskOwner`, `AssignedTo`, `Owner` | The rating being current, the status being truthful, the issue reaching Resolved |
| `GOV Programme Leads` | The group, three to six people | Authorising or withdrawing every service request, and every change to the programme spine |
| `GOV Accountability Maintainers` | The group, deliberately wide | Confirming and correcting the rows they are named on, and the stakeholder vocabulary |
| `GOV Request Handlers` | The group, the provider staff who work requests | Picking up, progressing, handing back and closing service requests, and the minutes recorded on each |
| Contract manager | *(e.g. the owner of the shared-service agreement)* | Escalations at levels 3 and 4, and the evidence file at the agreement review |
| Site Owners | n/a | Group membership, deploys, and the manual go-live steps |

**Who leads a workstream is a register row, not a column.**
`GOV_Workstream` carries no person column on purpose. A `Lead` column
would give the programme two answers to one question, and it would be the
answer with no confirmation cadence, no escalation route and no review
status, so it would go stale the first time a lead changed. The answer
comes from the activity row carrying `ActivityRole`, and the *Workstream
leads* view is where it is read.

**Being named in a person column grants nothing; being in
`GOV Accountability Maintainers` does.** Site members hold Read on the
three accountability lists, so somebody named Accountable on forty
activities who is not in that group cannot confirm one of them, cannot
correct a row they know is wrong, and cannot flag it *Needs review*. That
makes the group's membership a control in its own right, and the deployer
neither declares nor reconciles group membership, so keeping it in step
with the current Responsible and Accountable population is quarterly human
work.

## The reading cadence

| Cadence | Who | What is read |
| --- | --- | --- |
| Daily, no meeting | The triage owner | *Needs triage*; assign a workstream and owner to each row |
| Weekly, no meeting | Everyone named on a row | *My actions* and *My accountabilities*, ten minutes alone |
| Fortnightly | Programme owner and the workstream leads | Open issues; *In progress* and *Authorised, not yet picked up*, checking every authorised request names an `AuthorisedBy` and every request In progress names an `AssignedTo`; overdue actions; risks due for review; *Awaiting decision* and *Stalled proposals*; decisions made today |
| Monthly | Steering group | *The programme*; the full risk log worst first; *Closed this quarter*; *Escalated* and *Needed soon or overdue*; the graduation check; *Awaiting decision*, and the three decision reconciliations in `50-govern/reporting-joins.md` |
| Quarterly | Register owner and governance | The accountability register, in the nine steps below |
| Annually | Sponsor and governance | The workstream set, the stakeholder vocabulary, the escalation counts, the minutes spent on closed requests and the adoption measures |

**Plus one trigger that is not a cadence: any material organisational
change runs the affected part of the quarterly review immediately.** That
half is inherited from `raci-matrix` and it is the half that gets skipped.
Material change means at least a restructure, a senior appointment or
departure, a forum created or disbanded, a service moved between teams, a
new statutory or funding obligation, a change of provider personnel on the
shared-service agreement, and any incident review that found nobody was
clear who owned something.

The per-row `ConfirmationDue` cadence (Statutory 6 months, High 12, Routine
24) is the floor rather than the review schedule. It is the longest a row
may go unexamined, and a register reviewed only when rows fall due drifts
for up to two years in its Routine half.

### What a quarterly review consists of

1. **Work the *Confirmation due* view.** Everything falling due in the next
   thirty days or already past. Each row is re-read, corrected if it needs
   it, then confirmed: `LastConfirmed` to today and `ConfirmedBy` to
   whoever actually checked. An edit is not a confirmation.
2. **Work every *Needs review* row.** These are the rows a human has said
   are wrong. They are the highest-value rows in the register and they
   should not survive two consecutive reviews.
3. **Read *By workstream*.** Each lead reads their own accountabilities as
   a block. The rows with no workstream are the programme-wide bucket and
   are read as one group.
4. **Read *Workstream leads*.** Each workstream should have exactly one
   current lead, and the count is taken against `GOV_Workstream`'s own
   rows rather than against the view. A workstream with two leads shows as
   two rows under one heading; a workstream with none shows nothing at all,
   because an absent group has no heading.
5. **Read *Decisions and approvals*, grouped by `AccountableForum`.** Every
   non-Task row should name an escalation route that reaches somebody, and
   the forum it groups under should still exist. This is also where an
   External stakeholder holding an accountability becomes visible, as its own
   group heading.
6. **Read *Consultation load*, grouped by stakeholder.** The overload detector.
   One stakeholder consulted on everything is invisible in any activity-first
   view, because three consultations per row look reasonable everywhere.
   Challenge any stakeholder over six consulted or agreeing involvements;
   write the number in, because a vague sense of "a lot" is never challenged.
7. **Check *Active stakeholders* against the org chart.** Anybody who has left,
   and any forum disbanded, gets the departed-person workflow below. The
   view carries both `Contact` and `ServiceDeskAddress` so a blank of
   either kind is visible while reading.
8. **Look for the activities that are not there.** No view can show an
   absent row, so this is a walk along three axes: each workstream, in
   turn, for statutory or high-consequence work nobody wrote down; the
   programme-wide bucket, for who chairs, who reports and who signs off;
   and the provider boundary, for work that happens between the two
   organisations and belongs to neither register. The third axis is the
   one most likely to fail, because work between organisations is nobody's
   default responsibility.
9. **Read version history and reconcile group membership.** See
   "Self-service confirmation" below.

## Two checks no save rule can make

Both are human work, both are stated here rather than implied, and neither
is a gap somebody forgot to close. SharePoint validation formulas refuse
multi-line and person operands outright, which is where each of these dies.

**1. Every closed risk carries a closure note.**

`ClosureNote` is rich text, and a validation formula cannot reference a
multi-line column at all. The build refuses to write such a rule rather
than emitting one that silently never fires, and `mapping.yaml` says so at
the place somebody would add it. A closed risk with an empty closure note
saves cleanly today and will keep saving.

The control is the *Closed this quarter* view, read **monthly** at the
steering group. It filters on `ReviewDate` within the last ninety days,
because closing a risk is a status change and there is no closure date to
filter on, and it renders `ClosureNote` as a column so a blank is visible
while reading. This is `raid-log` governance rule 2, unchanged.

**2. Every authorised service request names the person who authorised
it, and every request being worked names its handler.**

`AuthorisedBy` and `AssignedTo` are person columns, so the same refusal
applies to both. The enforceable half of the authorisation obligation is
kept: `AuthorisedDate` is required from `Authorised` onwards by the list
rule, `AuthorisedDate` cannot be in the future by its own column rule, and
both fields appear on the form together in exactly the states the rule
fires in, so somebody entering the date is looking at the person field.

The control is the two views read together at the **fortnightly**:
*Authorised, not yet picked up* for requests no handler has taken, and *In
progress* (which renders `AssignedTo`) for requests the provider holds. An
authorisation record whose authoriser is blank is the one thing the
internal-authorisation control cannot survive, because the assertion at an
audit is a named person on a dated record, and a request In progress with
no handler is one nobody is working.

Two more checks of the same shape live in "The provider boundary" below: an
External stakeholder names a `ServiceDeskAddress` while every other non-Forum
stakeholder names a `Contact`, and the provider is never the Accountable. Both
are refused for the same reason and both have a view behind them.

## The departed-person workflow

Somebody leaves, a role is abolished, a forum is disbanded, or the provider
changes the person who holds the account. Work it in this order.

1. **Set the `GOV_Stakeholder` row to Inactive.** `Status` drives
   *Active stakeholders* and *Retired stakeholders*, so this is what takes the stakeholder
   out of every picker's working view.

   **Whether you also update `Contact` depends on `StakeholderKind`.** For a
   Role, Forum or External stakeholder the row's identity is the position, the
   committee or the organisation, and that has not changed, so point
   `Contact` at whoever now holds the role or chairs the successor forum.
   For an **Individual** stakeholder the row *is* that person, and repointing
   `Contact` at their successor silently rewrites history, because every
   activity and involvement naming that stakeholder now resolves to somebody who
   never held it. Leave an Individual's `Contact` alone, create a new
   active Individual stakeholder, and repoint the current rows at it.
2. **Never delete a stakeholder row.** `Activity.AccountableForum`
   and `Involvement.Stakeholder` are lookups at it, and deleting the
   row orphans them: the children survive pointing at nothing, which reads
   as a blank cell rather than as an error. `GOV Contribute No Delete`
   gives that posture a mechanism for maintainers, though governance and
   site owners still hold Contribute and can delete.
3. **Work the activities that named the person.** `Responsible` and
   `Accountable` are both columns on *By workstream* and *My
   accountabilities*, so the rows can be found by filtering or sorting.
   Reassign each to whoever now holds the work. This is the step that takes
   real time and it is the step that matters: an activity whose Accountable
   left three months ago is a row that reads as owned and is not.
4. **Work the involvements.** *By stakeholder* is grouped for exactly this.
   Repoint each involvement at the successor or retire it.
5. **Work the delivery layer, which `raci-matrix` does not have.** A
   departure leaves rows in four more lists, and none of them appears in
   any accountability view:

   | Column | List | What to do |
   | --- | --- | --- |
   | `AssignedTo` | `GOV_Action` | Reassign every open row, from *Open by person* |
   | `Owner` | `GOV_Issue` | Reassign every open row, from *By owner* |
   | `RiskOwner` | `GOV_Risk` | Reassign every open row, from *Open* |
   | `InternalAccountable` | `GOV_ServiceRequest` | Reassign on every request not `Closed` or `Withdrawn` |
   | `AssignedTo` | `GOV_ServiceRequest` | Reassign on every request `In progress` or `Waiting on requester`, and tell the provider |

6. **Do not rewrite a record of an act that has already happened.**
   `AuthorisedBy`, `EscalatedBy`, `RequestedBy` on a closed request,
   `ConfirmedBy`, and `DecidedBy` all say who did something on a date. A
   departure does not change that, and repointing one destroys the evidence
   the record exists to hold. Only forward-looking ownership moves.
7. **Reconcile `GOV Accountability Maintainers`.** Somebody who has left
   the programme leaves the group. Membership is not reconciled by the
   deployer, so nothing else will do it.
8. **Check the workstream leads.** If the departed person was a lead, the
   workstream now has none, and a workstream with no lead is invisible in
   *Workstream leads* rather than conspicuous in it. Count the groups
   against `GOV_Workstream`'s rows.
9. **Confirm each activity row you touched** (`LastConfirmed` and
   `ConfirmedBy`) so the cadence restarts from a row somebody verified.

A departure is also the moment to check the reverse direction: work the
person was doing that no register captured leaves with them, and nothing in
the register can tell you about it. Ask them.

## Self-service confirmation, and what it costs

The people named Responsible and Accountable can confirm and correct their
own rows. That is a deliberate reversal of `raci-matrix`'s posture, and it
is bought with an audit rather than with a gate.

**SharePoint cannot express "edit only your own row" against an arbitrary
person column.** The platform's item-level setting is "Create items and
edit items that were created by the user", it keys on **Created By** and on
nothing else, and an accountability row is typically created by a
maintainer during the initial build rather than by the person it names. The
setting would therefore grant edit rights to whoever typed the row and to
nobody the row is about. Its read-own half would be worse than useless
here, because a register nobody can read whole cannot be reviewed. The
deployer can neither configure nor assess the setting.

So the mechanism is four things together, and none of them works alone:

- **A deliberately wide group.** `GOV Accountability Maintainers` holds
  `GOV Contribute No Delete` on `GOV_Activity`,
  `GOV_Stakeholder` and `GOV_Involvement`. Membership is every
  person currently named `Responsible` or `Accountable`, plus governance.
- **No delete and no version pruning.** The level omits `DeleteListItems`
  and `DeleteVersions`, so the worst a disagreement can produce is a row
  that changed, visibly, twice.
- **Deep version history.** Versioning is on across the family, with 200
  major versions retained on the three accountability lists and 100
  elsewhere. Every edit leaves an entry naming who made it.
- **The quarterly read.** The register owner reads version history on every
  row changed since the last review, and reconciles the group's membership
  against the current Responsible and Accountable population.

**The cost is real and is accepted.** Anyone in the group can adjust their
own row, and the register's authority rests on a review rather than on a
gate. What it buys is that the design stops asking people to maintain rows
they cannot change, which is the arrangement most likely to leave the
accountability layer stale.

**The version-history read covers five lists, not three.** Add
`GOV_Decision` to the read, where a rewrite is possible and
visible only in history, and `GOV_ServiceRequest`, where a deleted row
removes an internal authorisation record from the list whose whole purpose
is to hold them.

`GOV_Decision` is the one list where **no principal short of a list
administrator can delete a row**: governance, the owner group and the member
group all hold `GOV Contribute No Delete`. The list holds proposals as well
as decisions now, and a proposal is exactly the thing somebody tidies away
when it is inconvenient. `Withdrawn` is the honest way to end one, and it
leaves a row. Governance keeps Contribute on `GOV_ServiceRequest` instead:
a duplicate request is an ordinary thing, a deletion by one of three to six
trusted people is recoverable from the recycle bin within its retention
window, and the review is already reading history on four other lists that
quarter. The handlers hold `GOV Contribute No Delete` there, because a
handler tidying the queue is the deletion hardest to notice.

### The probe this posture needs before go-live

`GOV Submit Only` is `change-register`'s measured eight permissions,
unchanged. **`GOV Contribute No Delete` is not itself a measured
precedent.** It is composed from one by adding `EditListItems` and
`OpenItems`, and this tool does not ship a permission claim it has not
seen work. Run this on the live site before anybody is told the audit
exists, and record the result here with its date:

1. Grant `GOV Contribute No Delete` to a second account on a test list.
2. Confirm that account can open an item, edit it and save it, and that the
   modern list page and the Edit form both render.
3. Confirm delete is not offered to it, in the command bar and in the item
   context menu.
4. Confirm it cannot prune version history, both from the version-history
   pane and through the API.

Steps 3 and 4 are the ones the whole posture rests on. If version history
can be pruned by a maintainer, the audit is advisory and the group must be
narrowed instead.

## The decision route

`GOV_Decision` holds two things in one list: proposals no forum has
answered yet, and decisions that were made. `Status` is the only column
separating them, which is why it is indexed, why it carries the one formatter
on the list, and why the default view is the queue rather than the log.

`Activity.DecisionRoute` records where a standing activity's
proposals are **meant** to be decided. `Decision.DecidedByForum`
records where a decision **was** made. The two disagree in practice, and
the disagreement is the interesting part.

### The two limbs of s 65S(2)

A Victorian health service board advises the Secretary of decisions of the
kinds the Health Services Act 1988 names, s 65S(2)(i) among them, and the
same subsection carries a separate obligation about risks. **The two limbs
ask for different things and the register should not merge them.**

- **Decisions attract advice.** What matters is that the decision was made,
  by which body, and that it was passed on. `DecidedByForum` and
  `RecommendedByForum` are what make that traceable. There is no clock in
  this limb.
- **Risks attract timeliness.** What matters is how quickly something was
  raised once it was known. `GOV_Risk`, its review dates and the
  overdue formatting on them carry that half. No decision column substitutes
  for it, and a decision recorded promptly is not evidence that a risk was.

An adoption programme is not the board, and little that happens here rises to
a matter the Secretary is advised of. The shape is kept anyway because the
programme's decisions feed the papers that do rise to it, and a decision with
no recorded forum cannot be traced up to the body that carries the duty.

### Prior approval and after-the-fact advice

Advice under s 65S(2)(i) is given **after** a decision is made. It is not an
approval gate, and nothing in this family should be described as one. Where a
separate instrument does require approval before acting, the decision row is
not that control: it is the record that the decision happened, and the
approval lives wherever that instrument says it does. Confusing the two
produces a programme that believes a typed row cleared it to proceed.

`RecommendedByForum` beside `DecidedByForum` is the committee-recommends,
board-decides shape the Act treats as the default (s 65S(2)(j)). A row where
both name the same forum is a recommendation a body accepted from itself,
which is a reporting exception rather than a save error.

### What this route does not do

It records where a standing activity's proposals are meant to be decided,
what rule that forum uses, what was asked, which forum actually decided, and
which actions followed. It **cannot** prove the forum that decided was the
forum entitled to decide, because SharePoint cannot compare two lookups
across two lists at save. It cannot enforce a delegation threshold, and it
cannot guarantee the recommend-decide-perform chain is complete. It can only
show where that chain is broken. Every one of those is a reporting
reconciliation or a human check on a named view, and none of them is a rule.

## What is enforced, and how

Every rule the family imposes, classified once. **Enforced at save** means
SharePoint refuses the write. **Enforced by permission** means the person
cannot reach the action. **Human cadence** means somebody checks it on a
schedule. **Guidance only** means it is text nothing checks, which is worth
classifying honestly rather than counting as a control.

### Enforced at save

| Rule | Mechanism |
| --- | --- |
| Every action, risk, issue and service request belongs to a workstream | `not null` lookup |
| Every action names one person and carries a real date | `not null` person, `not null` date. A person column holds one person, so "the team" is not expressible |
| An action cannot have been completed in the future | `column_validation` on `CompletedDate`, own message |
| A Done action has a completed date | `list_validation` on `Action` |
| Every risk has a likelihood, a consequence, an owner and a next review date | `not null` |
| A risk's rating and score are never typed | `calculated_text` and `calculated_number`, so there is nowhere to type a rating that disagrees with the matrix |
| Every issue has an owner and a raised date | `not null` |
| An issue cannot have been resolved in the future | `column_validation` on `ResolvedDate`, own message |
| A Resolved or Closed issue has a resolved date | `list_validation` on `Issue` |
| Every activity has exactly one Responsible and one Accountable | `not null` person columns. The arity is the column type, not a rule |
| A Decision, anything Statutory, and anything carrying an `ActivityRole` names an escalation route | `list_validation` on `Activity`, three branches sharing one message |
| A confirmation cannot be dated in the future | `column_validation` on `LastConfirmed`, own message |
| A stakeholder title is unique | `unique` on `Stakeholder.Title`, which stops two spellings of one forum splitting every grouped view |
| Every service request has a needed-by date and an internal accountable person | `not null`. The second is where accountability stays inside the health service |
| A request Authorised, In progress, Waiting on requester or Closed carries its authorisation date | `list_validation` on `ServiceRequest`, branch 1 |
| A Closed request records the minutes spent on it | `list_validation`, branch 2 |
| An escalation records both a level and a date | `list_validation`, branches 3 and 4 |
| An authorisation or an escalation cannot be dated in the future, and minutes spent cannot be negative | `column_validation` on three columns, own messages |
| Every proposal carries the date it was raised | `not null` date defaulting to today on `Decision.RaisedDate`, which is what lets the queue be sorted and aged |
| A decision that has been made carries the date it was made | `list_validation` on `Decision`, one branch. `Proposed` and `Withdrawn` are the two states it does not fire in |
| A decision cannot have been made in the future | `column_validation` on `DecisionDate`, own message |

`GOV_ServiceRequest` has **four** validation branches, and they share one
message, because a list has one `ValidationFormula`. Two more, requiring
`AuthorisedBy` from Authorised onwards and `AssignedTo` from In progress
onwards, were written into the design and cannot be built: the build
rejects a person operand as `condition_operand_type_unsupported`. Both
obligations are check 2 above.

### Enforced by permission

| Rule | Mechanism |
| --- | --- |
| Only governance edits the programme spine | Class A on `Workstream`, members Read. A phase change is a programme decision and should arrive with one |
| A submitter cannot create an already-authorised or already-assigned service request | `form_visibility`: `Status`, `AuthorisedBy`, `AuthorisedDate`, `AssignedTo` and `MinutesSpent` are off the New form |
| A requester cannot edit their own service request afterwards | `GOV Submit Only` for members on `GOV_ServiceRequest`. Governance corrects, and the handlers work the row through `GOV Contribute No Delete` |
| A maintainer cannot delete an activity, a stakeholder or an involvement, and a handler cannot delete a request | `GOV Contribute No Delete` omits `DeleteListItems` |
| Nobody short of a list administrator can delete a decision or a proposal | The same level, held by all three principals on `GOV_Decision`. `Withdrawn` is how a proposal ends |
| A maintainer cannot prune version history | The same level omits `DeleteVersions`, which is what makes the audit an audit |
| Nobody can hand-grant access that survives | `reconcile: exact` on every list |
| Nobody can change the schema through the UI | `seal_columns: true`. Friction and tamper-evidence, not enforcement |
| No list can be deleted through the UI | `prevent_list_deletion: true` |

The two form-visibility rules and the permission level are halves of one
control. Neither works alone: a submitter who can pick their own status can
authorise their own request, and a submitter who can edit the row
afterwards can authorise it a moment later.

### Human cadence

| Rule | When | Why it cannot be enforced |
| --- | --- | --- |
| Every closed risk carries a closure note | Monthly | `ClosureNote` is rich text and validation formulas refuse multi-line operands |
| A risk is genuinely reviewed rather than date-bumped | Monthly | SharePoint can require a date; it cannot require a thought |
| A risk that has outgrown the programme graduates | Monthly | `raid-log`'s four criteria, and it is a copy rather than a move |
| No action is filed against a closed workstream | Fortnightly | A lookup picker cannot be filtered, so the `WorkstreamPhase` projection makes the mistake visible instead of preventing it |
| Every decision is typed in before the meeting ends | Fortnightly | The discipline most likely to lapse, and the one with the highest cost when it does |
| No proposal sits past two meeting cycles | Fortnightly | *Stalled proposals* shows them at 42 days. Whether a stall is neglect or a deliberate hold is a judgement no filter makes |
| The forum that decided was the forum entitled to decide | Monthly | A validation formula reads one row on one list. Comparing `Decision.DecidedByForum` with the `DecisionRoute` on its activity crosses two lookups and two lists, which SharePoint refuses |
| A recommending forum did not also decide | Monthly | The same refusal, one list closer: it compares two lookup columns, which validation formulas cannot read |
| Every approved decision that needed an action has one | Monthly | A count across two lists, and "needed an action" is a judgement rather than a state |
| A phase change arrives with a decision, and a phase change is not made while a proposal about it is open | Monthly | Cross-list, and the second half asks about a row that may not exist |
| An authorised request is picked up | Fortnightly | Nothing on the provider side notices a request nobody holds. *Authorised, not yet picked up* is the guard |
| Every authorised request names an `AuthorisedBy`, and every request In progress names an `AssignedTo` | Fortnightly | Both are person columns and person operands are refused; read across *Authorised, not yet picked up* and *In progress* |
| An activity row is genuinely re-confirmed | Quarterly, floor of 6, 12 or 24 months per row | Same reason. `ConfirmedBy` at least records who claimed it |
| Every *Needs review* row is worked | Quarterly | A row a human has marked wrong cannot be detected by anything else |
| Exactly one current lead per workstream | Quarterly | Cross-row uniqueness is not expressible: a validation formula reads only the row being saved |
| Version history is read on every row changed since the last review | Quarterly | The audit that replaces a read-only posture on the accountability layer |
| `GOV Accountability Maintainers` matches the Responsible and Accountable population | Quarterly | Group membership is neither declared nor reconciled by the deployer |
| The activities that are not there | Quarterly | No view can show an absent row |
| An External stakeholder names a `ServiceDeskAddress`, and every other non-Forum stakeholder names a `Contact` | Quarterly | `Contact` is a person column, and "required unless StakeholderKind is Forum" is the same refusal for the same reason |
| The provider is never the Accountable | Quarterly | Person and lookup operands are both refused |
| Consultation is not concentrated on one stakeholder | Quarterly | A judgement about a distribution, which no formula reads |
| Narrative fields are sampled for identifiable content | Quarterly, programme owner | Multi-line columns cannot be validation operands, and a length measure is refused in conditions |
| Escalation levels 3 and 4 are counted, and the minutes spent on closed requests are totalled | Annually | The programme's evidence at the agreement review; *Closed* carries the total |
| Attachments are disabled on all ten lists | At deploy, and after any list-settings change | There is no `attachments` key in `mapping.yaml`, and the deployer neither sets nor reconciles the setting |
| The site home page and navigation are built and verified | At deploy | The bundle provisions lists, views, forms and permissions, and has no site-home or navigation declaration |

### Guidance only

| Text | Where | What it is not |
| --- | --- | --- |
| "Nothing patient-identifiable belongs in any field on this form" | The form headers on `GOV_Issue`, `GOV_Risk` and `GOV_ServiceRequest` | Not a control, not a cadence, and not something anything checks |

Classifying it honestly matters. A static form header is read once and then
stops being read, so calling it a control at every save would imply an
active check that does not exist. What actually defends the healthcare
boundary is elsewhere: each of those three lists carries exactly one
narrative column and the rest of the record is choices, dates, people and
references; attachments are disabled as a blocking go-live gate, because
the realistic leak is a screenshot rather than prose; and the programme
owner samples the narrative fields quarterly, which is the only one of the
four that can catch a disclosure that has already happened.

## Change control

### The confirmation cadence

The cadence is one formula in `20-configure/mapping.yaml`, under
`calculated_formulas`. **Editing it recalculates every existing row.**
SharePoint recalculates a calculated column across the whole list the
moment the formula text changes, and a redeploy is exactly that change.

- **Shortening an interval falls due immediately.** Taking Routine from 24
  months to 12 does not schedule a gentler future; it makes every Routine
  row confirmed more than a year ago overdue the moment the paste finishes,
  with the overdue treatment on all of them. That may be what you want.
  Plan the review capacity for it rather than discovering it.
- **The formula is keyed to `adopt_criticality` by name.** It maps
  *Statutory* and *High* explicitly and treats everything else as Routine,
  so a member added, renamed or reordered in `schema.dbml` silently
  receives the **longest** interval rather than failing. Change the enum
  and the formula together, or neither.

Export `GOV_Activity` to Excel before any cadence change. That
snapshot is the only record of the due dates as they stood before it.

**The month-end overflow is inherited on purpose and is not fixed here.**
Adding months with `DATE(YEAR(d), MONTH(d)+N, DAY(d))` overflows rather
than clamping, so a confirmation recorded on 31 August falls due on 3 March
rather than 28 February. It is one to three days on a cadence of six months
or more, against a column whose own guidance is to re-confirm sooner on any
material change. The same formula is in `raci-matrix` and `risk-register`,
and it is tracked as `raci-matrix` issue #5. Fixing it in one of the three
families forks a defect that should be fixed once, upstream, and the
arithmetic that clamps correctly is substantially longer and recalculates
every row to install. Read that issue before touching it here.

### The risk matrix

The 5x5 matrix is carried from `raid-log` unchanged, and the argument for
keeping it that way is worth stating before somebody improves one cell. The
same matrix is used by `risk-register`, so a programme risk and an
organisational risk mean the same thing by "High", and a risk graduating
from this family to the organisational register does not need re-rating on
arrival. Changing a cell here breaks that alignment as well as re-rating
the log.

**Editing a cell recalculates every existing row**, for the same reason the
cadence does, and this family carries no `MatrixVersion` guard. A row rated
under the old matrix is silently re-rated by the new one with no record
that it was ever rated differently. `raid-log` accepts that trade because a
project log is archived with the project; a programme running for two years
or more is more likely to outlive a revision of the matrix, so the
discipline here is stricter rather than looser:

1. Set the matrix **before first deploy**, or accept that changing it
   re-rates history.
2. If a cell must change mid-programme, export `GOV_Risk` to Excel
   first. That snapshot is the only record of the ratings as they stood.
3. Update the ASCII matrix table in the comment above
   `calculated_formulas` to match the cells you changed. It is what the
   next person reads before touching one.
4. Bump `schema_version` in `release.yaml`, rebuild, redeploy, and tell the
   risk owners their ratings moved.

Both formulas are keyed to exactly the five `adopt_likelihood` and five
`adopt_consequence` members, in the order the schema declares them: the
nested IFs match the first four by name and treat everything else as the
fifth. An added, renamed or reordered member therefore rates as the worst
case, silently, rather than failing. The matrix is 5x5, so changing either
enum means rewriting all 25 cells anyway.

### The escalation-route rule and its form condition

`GOV_Activity` carries a three-branch save rule: a Decision,
anything Statutory, and anything carrying an `ActivityRole` all need an
`EscalationRoute`. The third branch is this family's addition, on the
reasoning that a standing position with no tie-break is the position that
stalls at the worst moment.

**The rule and the form's visibility condition must be edited together.**
`form_visibility` shows `EscalationRoute` under an `any_of` of the same
three conditions, so the field is on screen exactly when it is mandatory. A
visibility condition narrower than its rule produces a form that will not
save and will not say why, and **no gate this tool runs catches it**.

Two consequences of how the third branch is written. It fires on
`ActivityRole is_not_null`, so a fourth member added to
`adopt_activity_role` is covered automatically and a member renamed stays
covered. And `ActivityRole` is deliberately a separate column from
`ActivityKind`: folding a role into `adopt_activity_kind` would look
tidier and would silently widen the first branch, which fires on
`GOV_Decision`.

## The provider boundary

The tenant belongs to a shared service provider. The health service
operates sites and lists and can run flows; Entra groups, conditional
access, Power Platform environments, licensing, app registrations, DLP
policy and tenant-wide settings all go through the provider. That boundary
is the programme's largest source of schedule risk, which is why it is
recorded rather than narrated.

### One row, two owners

`GOV_ServiceRequest` is the request surface. A change the provider has to
make is asked for, authorised, worked and closed on one row, and the row
has two owners in turn. The health service owns the first half: what was
asked for, why, who authorised it internally and when it is needed. The
provider's handler, a member of `GOV Request Handlers`, owns the second:
who holds it, where it is, and the minutes spent on it. Nothing is copied
between two records, because there is one.

| Step | Where | Who |
| --- | --- | --- |
| 1. The record | `GOV_ServiceRequest`, `Status: Drafted` | Anyone on the site, under `GOV Submit Only` |
| 2. Internal authorisation | `Status: Authorised`, `AuthorisedBy`, `AuthorisedDate` | `GOV Programme Leads` only |
| 3. Pick-up | `AssignedTo`, `Status: In progress` | The handler, or governance naming one |
| 4. The work | `Status: In progress`, or `Waiting on requester` when the handler needs something from the health service | The handler |
| 5. Closure | `Status: Closed`, `MinutesSpent` | The handler. `Withdrawn`, set by governance, ends a request the programme no longer wants |

**The health service's assertion at an audit is not "our SharePoint list
says approved".** It is that this request was authorised internally by
this named person on this date, and here is the record and its version
history. That is why check 2 above exists and why
`GOV_ServiceRequest` is on the quarterly version-history read.

**The gap between authorisation and pick-up has one guard.** A request
authorised in the list that no handler has taken is one the provider is
not working, and nothing on their side would notice. The guard is the
*Authorised, not yet picked up* view, read at the fortnightly. A `Drafted`
row older than one check-in cycle is the same failure one state earlier,
and the same read catches it.

### Where the provider lives in the model

The provider is one row in `GOV_Stakeholder`, with `StakeholderKind: External`
and `Status: Active`. Its `Contact` stays **blank** and its
`ServiceDeskAddress` carries the provider's service desk address or queue,
for anything that does not belong on a request row.

That is a deliberate exception to the ordinary contact rule, and it has two
halves. Naming an external engineer in `Contact` invites every reader to
treat them as the owner of the thing, and a person column would imply the
recipient is accountable for the request. Leaving the stakeholder unreachable
would be the other failure, because a name nobody can act on is not a
vocabulary entry. So: **an External stakeholder names a `ServiceDeskAddress` and
leaves `Contact` blank; every other non-Forum stakeholder names a `Contact`.**
Both columns render on *Active stakeholders*, and a maintainer scanning that
view each quarter is the whole enforcement mechanism, because `Contact` is
a person column and validation formulas refuse person operands.

**The provider is never the Accountable.** Every activity concerning a
tenant-level change names an internal person as `Accountable`. The provider
appears, if at all, as a Consulted or Informed row in
`GOV_Involvement`, which is what an external stakeholder is in a RACI.
No save rule can catch a breach, because `Accountable` is a person column
and `AccountableForum` is a lookup and both operand types are refused, so
the control is *Decisions and approvals*: an External stakeholder holding an
accountability appears as its own group heading in the pack the quarterly
review already reads. Visible, not prevented.

**The escalation route stops at the boundary.** The `EscalationRoute` text
on any activity covering service requests names the internal rungs only,
because that is all the register can commit anybody to. What records a
crossing once it has happened is the four-level ladder below.

### The four escalation rungs

| Level | What it is | Initiated by | Recipient | Counted at the agreement review |
| --- | --- | --- | --- | --- |
| `1 Program` | The programme owner chases the request | Programme owner | Provider service desk lead | No |
| `2 Directorate` | The health service's digital or IT director raises it | That director | Provider service delivery manager | No |
| `3 Contractual` | Raised formally under the shared-service agreement | Contract manager | Provider account or contract lead | **Yes** |
| `4 Executive` | Formal notice between the two organisations | Sponsor or executive | Provider executive | **Yes** |

Levels 1 and 2 are operational. Levels 3 and 4 are contractual: a
conversation between two organisations under an agreement, which moves at
the speed of an agreement rather than of a programme. A programme that
treats level 3 as an ordinary escalation will keep pulling it and keep
being surprised by the response time.

**`EscalationLevel` is a high-water mark, not a history.** A request
escalated at level 1 and later at level 3 keeps only level 3 on the row,
and the sequence is in version history. That trade is taken because the
metric the annual review needs is a count of requests that reached levels 3
or 4, not a count of escalation events. Build a separate
`Escalation` list only after a year in which more than a
handful of requests were escalated twice at different levels, which is the
first point at which the sequence starts mattering to the argument.

**Why the list exists at all, stated once.** An organisation that cannot
count what an arrangement costs it cannot renegotiate the arrangement. The
annual count of levels 3 and 4, beside the minutes spent on closed
requests, is the health service's evidence at the shared-service agreement
review, and it is worth more than the operational visibility the list also
provides.

## Sealed columns, deletion protection and attachments

This family uses the fleet-standard hardening declared in `mapping.yaml`.
`seal_columns: true` blocks UI schema edits and column deletion on every
deployed column, even for site admins, and a display-name rename still gets
through as drift that the next re-paste reverts and reports.
`prevent_list_deletion: true` removes "Delete this list" from all ten
lists for everyone. Both are friction and tamper-evidence rather than
enforcement against a determined site collection administrator working
through the API. See "Hardening and drift detection" in
[`templates/README.md`](../../README.md). The deploy script unseals for its
own run and re-seals afterwards, and `rollback.js.txt` clears deletion
protection per list after you confirm that list.

**Attachments are the gap those two do not close.** There is no
`attachments` key in `mapping.yaml`, the deployer neither sets nor
reconciles the setting, and disabling attachments on all ten lists is a
manual step in `30-deploy/deploy.md` with a line in the verification
checklist. For a family carrying a healthcare boundary that is the
uncomfortable one, because it is the **only** privacy control a redeploy
does not reassert: if somebody re-enables attachments in list settings,
nothing detects it and nothing repairs it. Re-run that step after any
change to list settings, not only at go-live.

## Retention and closure

**Nothing is deleted in flight.** Closed risks, dropped actions, resolved
issues, retired activities and inactive stakeholders are the entire content of a
lessons session, and a register pruned to its live rows cannot answer what
the programme already dealt with. Retire instead: `ReviewStatus: Retired`
on an activity, `Status: Inactive` on a stakeholder, `Dropped` on an action.

### The retention decision, and whose it is

**The retention class and disposal authority for these records is a
decision for the health service's records manager, under its own records
disposal authority.** This template does not make it and cannot. What it
does is name what has to be classified, so the decision is taken rather
than left to whoever turns the site off:

| Record | Why it is not ordinary programme ephemera |
| --- | --- |
| `GOV_ServiceRequest` and its version history | The internal authorisation for changes made in a tenant the service does not own, and the evidence at a contractual review. The history is the audit of who authorised what, who worked it, and when |
| `GOV_Decision` and its version history | The programme's decision record, including any decision to accept a measurement gap. It now holds the proposals as well, so the history is the audit of what was asked, what was decided, and what changed between the two. No principal short of a list administrator can delete from it |
| `GOV_Activity` and its version history | Who answered for what, and the audit of self-service confirmation |
| `GOV_Risk` | Including risks graduated to the organisational register, whose copy there does not carry the programme's own history |
| Any phase-2 flow definitions and their run history | What was automated, under whose identity, and whether it ran |

### Two rules not to reach for

Both of these get applied to a health service list by reflex, and neither
sets the class for these nine. Naming them here is not advice about what
does apply. It is a warning about the two wrong answers that arrive first.

- **HPP 4.2** sets a minimum retention for health information about an
  individual. Nothing on these lists is health information about an
  individual, the form headers and the quarterly sampling exist to keep it
  that way, and treating a programme decision log as though it were a
  clinical record produces a floor that is both wrong and reassuring.
- **PROS 12/05** is the other authority people reach for by name. Which of
  the health service's disposal authorities covers programme administration
  is the records manager's determination, made against the service's own
  instruments, and it is not settled by whichever number somebody remembers.

If either turns out to be the right answer, it will be because the records
manager said so, in writing, with a date. Record that here when it happens.

### The closure sequence

Run in this order, and record the whole sequence as one
`GOV_Decision` row before any of it is executed.

1. **Export all ten lists**, before anything is decommissioned. Where
   version history is the audit (the three accountability lists and
   `GOV_ServiceRequest`), export the history too. An Excel export of
   current rows is not the audit. Export `GOV_Involvement` with
   its lookups resolved, because an involvement exported without its
   activity and stakeholder is a sentence about an input with nothing attached.
2. **Graduate the unresolved risks.** Anything still open that outlives the
   programme goes to the organisational `risk-register` as a copy, on
   `raid-log`'s four criteria and its copy-not-move rule. Close the
   programme row with a closure note naming where it went.
3. **Graduate the standing accountabilities.** An `GOV_Activity`
   row describing work that continues after the programme is a
   `raci-matrix` row, and `raci-matrix` stays deployed and supported. Copy
   it, set its `Domain`, and confirm it there. The programme's copy stays
   as history.
4. **Close or hand over the service requests.** Anything still open moves
   to business as usual with a named owner, and its handler is told. The
   escalation counts and the minutes spent go to the contract manager as
   agreement-review evidence, in writing.
5. **Disable any flows before the site is archived**, remove their
   connections, and remove the automation identity from its group. A flow
   left running against an archived list either fails silently every week
   or, worse, keeps writing.
6. **Transfer site ownership** to whoever will hold the archive, and empty
   the two programme groups rather than deleting them, so the ACL
   declaration still reconciles if the site is ever redeployed.
7. **Decide the site's disposition**: retained read-only, archived, or
   deleted at the end of the retention period. Record which, and the date
   it takes effect.
8. **Never run `rollback.js.txt` against real rows.** It is for a failed
   first provision on an empty site, and for clearing demo data seeded with
   `--seed`.

## This register is not an HR record

`GOV_Activity` records how work is organised, not how people
perform. It carries no assessment of anybody and should never be used as
one: a row that falls due is a row nobody has re-read, not evidence about
the person named in it. Keeping that line clean is what makes people
willing to mark their own rows *Needs review*, and with self-service
confirmation in place that behaviour is the register's main defence against
going stale.
