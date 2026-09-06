# Approval tracking: a paper goes to three places (future work)

Design proposal for approval tracking in a programme-governance family,
written 2026-08-28 against the family that preceded today's
`programme-governance` solution. Its recommendations were subsequently
implemented in `programme-governance` (the `Agree` involvement role and the
`Decision.EndorsementRoute` column both exist in the shipped schema). Entity
names below use the predecessor's `Program` prefix; the successor family drops
it (`Decision`, `Action`, `Activity`, `Stakeholder`, `Involvement`,
`ServiceRequest`). Kept as future-work reference material.

The regulatory sections assume a Victorian public health service, which is the
assumption the whole family's governance document already rests on. A service in
another state should re-read sections marked Victorian.

## Verdict

**Record the route retrospectively. Do not build a live tracker. Do not spend
the tenth list.**

This is option 3 of the three offered, strengthened. Option 3 as stated
  (standing
`Agree` parties on `Activity` plus a `Detail` note) is right about the
standing half and wrong about the per-paper half, because `Detail` is the wrong
column for it and because leaving it unstructured means nobody writes it. The
proposal is therefore:

1. **Finish the `Agree` value that is already half-landed.** `involvement role
  choice`
   gained `Agree` in the working tree, and three of the four things that make a
   choice member real are still missing. No gate catches this.
2. **Add exactly one column**, `Decision.EndorsementRoute`, a `longtext`
   route record whose line format is taken from the endorsement table in OVIC's
   own PIA template. It costs zero joins, one non-lookup column, and no new
  list.
3. **Use the existing `Action` row for the in-flight chase.** The design
   already has the worked example for it.
4. **Case 1 (tenant-level change approved by several health services) needs no
  new
   structure at all.** Four published Australian precedents all resolve it
  without
   producing a multi-service artefact that a member service holds.
5. **Defer the tenth list** with a countable trigger and a reserved name,
  following
   the escalation-events precedent exactly.

Total cost: one DBML column, three one-line mapping edits, one demo row, one
  form
section, one test-fixture line, and edits to five documents. Measured build
  delta
below.

## Which problem this solves, stated plainly

The brief asks which of two things the design is for, and the answer is the
second one.

**It is a retrospective route recorder.** It answers "this paper went to
  Privacy,
then Cyber, then the steering group, and here is who signed and when." It does
not answer "this paper is with Cyber right now, Privacy has signed, Clinical
Governance has not been sent it yet."

The live-tracking question is not refused because it is unimportant. It is
refused because the person who knows the answer has no reason to open the list.
A live per-item tracker is only true if the approver updates it, and the
  approver
here is a privacy officer, a cyber lead or a clinical governance committee whose
work sits in email and in their own systems. The register would say "with Cyber"
for three weeks after Cyber signed. That is the same staleness argument the
schema already uses to refuse a `Workstream.Lead` column, and it is worse here,
because a stale approval state is not merely unhelpful, it is a false assurance
that somebody may act on.

The retrospective record has the opposite property. It is written once, at the
moment the decision is recorded, by the person recording the decision, who at
that moment necessarily knows where the paper went. That is the only moment in
the process when the fact is both known and cheap to capture. It is also the
  shape
the strongest published Australian precedent uses: Queensland Health's
  Enterprise
ICT Governance directive collects endorsement from every Hospital and Health
Service chief executive and then requires that **"The endorsement log** and any
other relevant supporting documentation must be provided" to the single
  approver.
The log is a record of a completed round, not a live board.

There is a third thing people usually mean by "live tracking", which is "chase
the one that is late". That is a task, not a state, and this family already has
  a
list for tasks.

ITIL 4 reaches the same conclusion from the operational side, and names the
alternative as an anti-pattern rather than a trade-off:

> "This sometimes leads to organizations establishing complicated, and often
> bureaucratic, systems of change authorization, with formal committees that
  meet
> regularly to overview and authorize changes accumulated over the period. These
> are known as change advisory boards (CABs), and they often become bottlenecks
> for the organization's value streams."
>
> "these controls would lead to ineffective and delayed change realization,
  which
> is unacceptable in today's complex environment."

ITIL 4's own answer is a single named change authority per change model, with
  the
role delegated to the appropriate level. It does not describe per-party approval
for shared infrastructure at all.

## Working-tree state, because it changes the recommendation

The v4 decision-route slice
(the predecessor family's decision-route design) has landed in the working tree
since the brief was written. As at 12:10Z, `Decision` carries `Status`,
`Activity`, `ResolutionSought`, `DecisionOutcome`, `RaisedDate`, a nullable
`DecisionDate`, `DecidedByForum`, `RecommendedByForum` and `LiveDecisionTitle`;
`Activity` carries `DecisionRoute` and `DecisionRule`; `Action`
carries `AuthorisingDecision`; and `involvement role choice` carries `Agree`.
  This
proposal is written against that state, not against the shipped commit.

Two consequences.

**The join arithmetic in the agreed spec is wrong and should not be copied.**
the predecessor family's decision-route design predicts the distribution
becomes `7->1, 8->3, 5->3`. Measured against the working tree by calling the
repo's own `all_items_joining_fields`, it is:

| Joins | Lists |
| --- | --- |
| 8 | `ServiceRequest`, `Decision`, `Activity`, `Action` |
| 5 | `Risk`, `Issue` |
| 4 | `Involvement` |
| 3 | `Stakeholder` |
| 2 | `Workstream` |

`JOIN_WARN_AT = 9` (`analysis/joins.py:82`) and `JOIN_LIMIT = 12`
(`analysis/joins.py:78`, measured 2026-07-31 at 6,000 items: 12 rendered, 13
refused with `SPQueryThrottledException -2147024749`). **Four of the nine lists
now sit one column below the warning band.** Four, not three, and the four
include the two lists an approval slice would most naturally want to extend. Any
approval design that adds a person column or a lookup to `Decision`,
`ServiceRequest`, `Activity` or `Action` trips
`JOIN_THRESHOLD_APPROACHED` on the spot. This is the single strongest argument
in the proposal, and it is arithmetic rather than taste.

**The working tree is currently red, for an unrelated reason.**
`test_every_formatted_column_is_exercised_by_a_demo_row[<family>]`
fails on `Decision.Status`, because the new enum has formatting and no
demo row yet exercises it. That is the in-progress slice's own remaining work,
not a defect this proposal introduces, but it means "the build is green" is not
currently a true statement about this family.

## Case 1: a tenant-level change that several health services must approve

**This case needs no new structure, and the reason is not a platform limit. It
  is
that the multi-service approval is not this health service's record.**

Four published Australian precedents bear on it. They differ in mechanism and
agree in result: none of them produces a multi-service artefact that a member
service holds.

**The closest structural analogue is a Victorian Rural ICT Alliance**, which is
the arrangement a regional Victorian health service is most likely to actually
  be
in. The Department of Health's *Rural Public Health Care Agencies ICT Alliance
Policy* (May 2026) makes membership compulsory ("All registered regional and
  rural
public health services, public hospitals, integrated community health centres
  and
multi-purpose services within the meaning of the Act, are required to be members
of the ICT Alliance in their region") and then puts approval authority in one
joint body rather than in the members severally:

> "The Executive Committee, has the authority to manage the ICT Alliance,
> including the power to make all approvals, decisions and determinations
  required
> or permitted to be given or made by the Members in the ICT Alliance."

The Executive Committee "is comprised of Chief Executive Officers (CEO)
representing ICT Alliance Members". The one place a per-member vote appears is
  the
annual program and budget, at "75 per cent of all ICT Alliance members holding
voting rights", and that vote is taken in the joint body, not collected as
signatures. The policy contains no per-change member sign-off and no
  deemed-assent
clause. Caveat on strength: the alliances' underlying Joint Venture Agreement,
which holds the operative voting and quorum clauses, is not published and was
  not
obtained.

**Where a change does reach across services, Victoria escalates it to a
departmental approver, not to per-service sign-off.** From the Department of
Health *Policy and Funding Guidelines 2025-26*, which are a binding condition of
subsidy:

> "Where there is ambiguity or where the scope of the project impacts another
> health service, health services must seek approval from the Digital Health
> Branch."

That is a single named external approver, and it is already expressible as a
`ServiceRequest` escalation plus a `Decision` row with `DecidedByForum` set
to the branch. The same guidelines add a genuine project gate that an M365
  program
may or may not cross: "All health service projects with an ICT component greater
than $1 million are to be subjected to departmental project assurance", reported
for inclusion on a public quarterly ICT dashboard. If this program crosses $1m,
that dashboard line is an external reference the register should cite, and
`ServiceRequest.IvantiReference` is the wrong field for it because it is not a
service-desk ticket. Record it in the `Decision` route instead.

**In a shared tenancy specifically, the published Victorian guidance gives a
member agency a notification right, not an approval right.** Public Record
  Office
Victoria, *Managing Records in Microsoft 365: A guide for Victorian public
offices*:

> "Victorian government agencies may either have their own tenant or be part of
  a
> multi-tenant 'VicGov' arrangement. Agencies in multi-tenant arrangements do
  not
> have access to the various administrative elements of Microsoft 365 which can
> limit their ability to access and implement various recordkeeping
> functionality."
>
> "Where an agency is part of a multi-tenant environment, it should seek details
> about its part of the tenant and is kept informed of all changes in the
> environment by the provider."

This matters for what the register may honestly claim. If the entitlement is to
  be
informed, a column asserting that this service approved a tenancy-wide change
records something the arrangement does not give it.

**Cenitex Collab365, the Victorian whole-of-government shared Microsoft 365
tenancy, resolves a tenancy-wide change through per-agency approval groups.**
  The
joint Cenitex and Public Record Office Victoria statement describes SharePoint
retention adjustments as "controlled by implementing a per department/agency
approval group", with a change "only actioned after a member of the department
  or
agency's approval group has approved it", taken "In consultation with the Shared
Tenancy Working Group". Source strength, stated honestly: `prov.vic.gov.au`
returns HTTP 403 to automated retrieval, so those phrases are corroborated at
  one
remove rather than read from the page. The surrounding structure is
  independently
confirmed by VAGO's *Cenitex: Meeting Customer Needs for ICT Shared Services*,
which records that Cenitex "defines its service arrangements in an MoU with each
customer" and "often needs to broker a common agreement between customers who
  may
have differing priorities and ICT strategies". Somebody should open the joint
statement manually before it is quoted in a paper that goes to a board.

The structure that follows is decisive for the schema, and all four precedents
point the same way. There is no single artefact that three health services
  jointly
sign. Either a joint body decides once on behalf of all of them, or each service
approves for itself and the operator actions the change when it holds what it
needs. In neither case is another service's assent this service's record.
Modelling it here would mean transcribing another organisation's governance into
  a
register whose own doctrine says the opposite:

> "The provider is never the Accountable" (`50-govern/governance.md:358`)

So case 1 maps onto columns that already exist:

- The health service's own approval is `ServiceRequest.AuthorisedBy` plus
  `ServiceRequest.AuthorisedDate`, which are already required from `Authorised`
  onwards.
- Where that authorisation needed a recorded decision rather than a routine
  sign-off, `ServiceRequest.AuthorisingDecision` points at the `Decision`
  row.
- The operator's side is `IvantiReference`, joined to the service-desk export,
  with the escalation ladder (`EscalationLevel`, `EscalatedDate`, `EscalatedBy`,
  `EscalatedTo`) covering the case where another service is the thing holding it
  up.
- Where the health service participates in a cross-service forum or alliance
  executive that agreed a tenancy-wide change, that is a `Decision` row
  with `DecidedByForum` set to the external body, which the working tree now
  supports.

The governance document already draws the boundary this sits on, and it is the
right one:

> "The health service's assertion at an audit is not 'our SharePoint list says
> approved'. It is that ticket INC-nnnnn was authorised internally by this named
> person on this date, and here is the record and its version history."
> (`50-govern/governance.md:498-502`)

### Do not build a deemed-approval clock, and here is the accurate reason

A "deemed approval if no objection within N days" mechanism would let case 1 be
modelled as a countdown rather than a set of sign-offs. It should not be built,
but not because the mechanism is unprecedented in Australia. It is precedented,
and a design document that says otherwise is wrong.

The direct multi-party precedent is the *Intergovernmental Agreement for the
Australian Consumer Law*, between the Commonwealth and all eight states and
territories:

> "16. Parties will have 35 days from the date of the Commonwealth Minister
> sending the notice to vote."
>
> "17. If a Party does not vote, or does not abstain, by the end of the 35-day
> voting period, that Party will be taken to have voted in favour of the
  proposed
> amendment."

It is also in statute for inter-agency assent. *Planning Act 2016* (Qld) s 58,
"Effect of no response": "If a referral agency does not comply with section
  56(4)
before the end of the period stated in the development assessment rules ... the
agency is taken to have given a response that the agency has no requirements
  for,
or advice about, the application." Section 29(8) of the same Act deems a local
government to have agreed. And the OAIC's statutory FOI Guidelines advise
  agencies
to tell a consulted State that "if no response is received it will be assumed
  the
State has no objection to release of the document".

Silence cuts the other way just as often. *Environmental Planning and Assessment
Act 1979* (NSW) s 8.11 deems a **refusal**, not an approval. Which way silence
runs is a policy choice, and Australia has drafted it both ways.

The reasons not to build one here are four, and they are specific:

1. **No published Australian shared-ICT arrangement uses it between peer
   agencies.** Every verified instance is either intergovernmental (ACL IGA),
   statutory planning (Qld), administrative consultation (OAIC FOI), or
  bilateral
   customer-to-supplier (below). The nearest real shared-tenancy analogue,
   Cenitex, does the opposite.
2. **The health sector's own agreements reject it.** The National Health Reform
   Agreement Addendum 2026-2031 requires that amendments be made "with the
   agreement of all Parties". National Cabinet's out-of-session process gives
  First
   Ministers three days and then escalates rather than deems: "In the event that
  a
   unanimous decision is not reached the item will be discussed at the next
   National Cabinet meeting." A member service objecting on principle has strong
   same-domain precedent.
3. **Every genuine instance has a second-notice gate that silence alone never
   satisfies.** The NSW Government ICT Agreement, clause 8.2(f), requires the
   supplier to serve "a written reminder notice" and only then starts a 10
  business
   day clock; clause 14.3(f) does the same with 15 business days. Queensland's
   deemed approval under s 64 requires the applicant to serve a deemed approval
   notice, copy it to every affected party, and wait a further 10 business days.
   A clock modelled without the second notice is not the precedented mechanism.
4. **It is contested even where it is offered.** In a published executed NSW
   agreement built on the ICTA template, the parties amended both clauses by
   deleting the deeming sentences outright. The template offers deemed approval
  and
   this government customer struck it.

A deemed-approval clock is also unimplementable in this family on its own terms.
The clock would need to compare a stored date against today at read time and
  drive
a state change, and nothing in the DSL does that: `column_validation` fires at
save, not on a schedule, and there is no flow.

## Case 2: an internal paper that routes to privacy, cyber and clinical

  governance

This is the case with real work in it, and it splits into three questions that
want three different answers.

### Who must sign, standing: `Agree` on the involvement enum

The agreed spec already answers this, and the working tree has already added the
enum member. `involvement role choice` now reads `Agree`, `Consulted`,
  `Informed`,
declared strongest first. `Agree` is RAPID's, meaning a veto that `Consulted`
  does
not carry.

**Three of the four things that make a choice member real are missing, and no
gate catches any of them.** Measured against the working tree:

1. `mapping.yaml:409` is
   `Involvement: { style: pill, map: { Consulted: low, Informed: neutral } }`.
   The enum has three members and the pill map has two, so an `Agree` row
  renders
   with no pill at all.
2. `mapping.yaml:696` still filters the "Consultation load" view on
   `{ field: Involvement, op: eq, value: "Consulted" }`. **The quarterly
  overload
   detector is therefore blind to the strongest form of involvement.** Its own
   comment says the failure it exists to reveal is "one party made Consulted on
   everything", and a party made `Agree` on everything is a worse version of
  that
   failure which the view will not show.
3. No demo row anywhere sets `Involvement: "Agree"`, so nobody deploying the
  demo
   data ever sees the value exist.

The reason nothing fires is worth writing down, because it is exactly the
  failure
class the project exists to close.
`test_every_formatted_column_is_exercised_by_a_demo_row` iterates the **map
  keys**
and asks whether a demo row produces each one. Its current failure message on
  this
family enumerates `Decision.Status (map keys ['Approved', 'Noted',
'Proposed', 'Ratified', 'Rejected', 'Withdrawn'])`, which confirms the direction
of the check. An enum member that is absent from the map is invisible to it. The
build is silent, the deploy is silent, and the column renders with a gap.

Adding `Agree` to a deployed, sealed column is safe. `Choices` is a member of
`DERIVED_FIELD_PROPERTIES` (`templates/deploy/_field_reconcile.js.j2:37-41`), so
it is a narrow MERGE with readback rather than an abort, and the deploy unseals
its own declared-seal fields for the run and re-seals afterwards. The comparison
is order-sensitive (`_field_reconcile.js.j2:170-175`), so appending is the safe
operation and reordering existing members is not.

### Where the paper actually went, per paper: `Decision.EndorsementRoute`

This is the one new column. It is a `longtext` on `Decision`, holding one
line per party the paper went to before it was decided.

**The line format is taken from OVIC's own PIA template**, which is the
jurisdiction-matched source and the one a Victorian privacy officer will already
recognise. Part 4 of that template is headed "Action items, endorsement,
  document
information" and contains an Endorsement table whose columns are **Name |
Position | Signature | Date**, prefaced:

> "The required endorsements for this PIA are listed below. This may include the
> program manager, a privacy officer, executive business owner, or any other
> responsible person."

The accompanying guide adds "It is up to you to decide whose endorsement is
required or appropriate." So the minimum a route line carries is the person,
  their
position, the date, and the fact of endorsement. A signature cannot be
  reproduced
in a text column, and the honest substitute is the reference of the document
  that
does carry it.

Queensland Health's Enterprise ICT Governance directive supplies the same shape
  at
the artefact level, and names it: endorsement is sought from every HHS chief
executive and Deputy Director-General, "The endorsement log and any other
  relevant
supporting documentation must be provided" to the Director-General as approver,
and the decision rule is a majority, not unanimity ("If the majority of HSCEs
  and
DDGs do not endorse the proposed minor amendments, the major review process must
be followed"). The Queensland Cabinet Handbook's Consultation Addendum is a
  third
instance of the same pattern, produced once at lodgement with no per-party
  status
enum, because by the time it is written the consultation is finished.

**A route line cites an assessment, it does not restate one.** Where a party's
endorsement rests on a separate document, the line carries that document's title
and location rather than its findings. This matters because the separate
  document
is the convention in every domain checked, and duplicating its conclusions into
  a
register is how the two versions start to disagree. OVIC's template is itself
document-controlled, with a block for "Document title, Document location,
  Document
owner, Document distribution, Related documents, Next review, Document version".
Note also that no Australian jurisdiction mandates a reference-number scheme for
these: the Commonwealth's published registers index by project title and record
only "Date the PIA was signed", so the route line should expect a title and a
  date,
not an identifier.

Three deliberate type choices:

- **`longtext` rather than `nvarchar`.** `nvarchar` maps to Text with
  `MAX_TEXT_FIELD_LENGTH = 255` (`analysis/limits.py:174`). Three route entries
  with a person, a position, a date and a document reference will not fit in 255
  characters, and a truncated evidence record is worse than none.
- **`longtext` rather than `richtext`.** Both map to a Note column, but
  `richtext`
  sets `RichText: true` (`analysis/typemap.py:515-518`) and therefore exports as
  HTML. This field is read back as evidence and pasted into reports, so plain
  text is the correct format. `longtext` gives `RichText: false` and
  `NumberOfLines: 6` (`typemap.py:510-514`).
- **Not a lookup and not a person column.** Both cost a join, and
  `Decision` is already at 8 of 12. The approvers here are also frequently
  roles, forums or external bodies rather than accounts in the tenant, which is
  the same reason `ServiceRequest.EscalatedTo` is text rather than a person
  column.

It cannot be conditionally required. `longtext` is a measured forbidden
  validation
operand (`condition_operand_type_unsupported`, from
`analysis/condition_rendering.py:374-396`), which puts it in the same class as
`ClosureNote` and for the same documented reason (`mapping.yaml:1224-1231`). Its
enforcement is a named human check, described below.

**The "optional blank on most rows" objection, answered directly.** That pattern
is rejected in this family, and the rejection is stated at
the predecessor family's design document: a column blank on most rows "is noise
  in every
view that renders it", or is "filled by obligation, so the register lies." The
escape here is precise rather than rhetorical. `EndorsementRoute` is **not
  rendered
in any view**. It appears on the item form only, in its own section, and the
"Decision log" view is untouched. A column that no view renders cannot be noise
  in
a view, and a column nobody is prompted to fill from a list surface is not
  filled
by obligation. This is the same treatment `Detail` and `ClosureNote` would get
  if
they were not already useful in a view.

**One shape that would be better and is not available.** The ideal record here
  is
append-only, so each line is stamped with its author and time by SharePoint and
cannot be rewritten afterwards. `AppendOnly` is hard-coded `False` for every
  Note
column at `generators/jsgen.py:883` and there is no mapping key for it. Adding
  one
is a fleet-wide DSL change with its own probe obligation, and it is out of scope
here. The substitute is list version history, which is enabled on every list in
this family and holds prior values of the column. State that substitute in
`50-govern` rather than implying the field is tamper-evident.

### What the three approvers are actually obliged to produce

This determines what a route line can point at, and the answers are not
symmetrical. Two of the three domains mandate no artefact at all for a Victorian
public health service, and the one register that is genuinely mandatory in all
three is the **risk** register, which this family already has as `Risk`.

**Privacy.** A PIA is not mandatory in Victoria. OVIC: "Although conducting a
  PIA
is not mandatory under Victorian privacy law, VPS organisations are required to
comply with Part 3 of the PDP Act." The mandatory-PIA-plus-published-register
regime is the *Privacy (Australian Government Agencies - Governance) APP Code
2017* ss 12 and 15, which binds Commonwealth agencies only and does not reach a
state health service. OVIC recommends a register without requiring one ("it is
also a good idea to keep an internal central register of PIAs") and suggests the
alternative this family can actually satisfy: "In some instances, it may also be
appropriate to include the privacy risk in your organisation's enterprise risk
register for greater oversight and management." The *Health Records Act 2001*
(Vic) contains the phrase "impact assessment" zero times. What binds is HPP 4.1,
an outcome standard: "An organisation must take reasonable steps to protect the
health information it holds from misuse and loss and from unauthorised access,
modification or disclosure."

**Cyber.** Victorian public health services are expressly excluded from Part 4
  of
the PDP Act by s 84(2)(d), (e) and (f), so the VPDSS, the security risk profile
assessment and the protective data security plan do not apply. VAGO states the
consequence directly: "Under section 84 of the PDPA, health services do not need
to comply with the VPDSS or its reporting obligations." Two carve-backs to check
locally: a s 84(3) Governor in Council declaration (not found, though the
  Gazette
was not exhaustively searched), and OVIC's caveat that an exempt entity
  performing
a public function on behalf of a regulated VPS organisation may still have Part
  4
obligations. What binds instead is organisational and periodic, from the *Policy
and Funding Guidelines*: an annual local cyber strategy shared with the
department, the mandated controls of the Health Sector Cybersecurity Maturity
Framework, and regular attestation "through online self-assessments (facilitated
through the Victorian Managed Assurance Authority)". None of that is a
  per-change
artefact. The ISM's authorisation-package model is the cleanest available
  template
if the service wants to borrow one, but the ISM says of itself that "An
organisation is not required as a matter of law to comply with the ISM, unless
legislation, or a direction given under legislation or by some other lawful
authority, compels them to comply", and its authorisation package is an
initial-authorisation artefact, not a per-change one.

**Clinical governance.** NSQHS accreditation is mandatory ("All Victorian public
health services must maintain their accreditation through the ACSQHC"), and the
action that covers this scenario asks for a consideration rather than a
  document:

> "1.05 The health service organisation considers the safety and quality of
  health
> care for patients in its business decision-making"

**That is the affirmative case for this column.** A recorded consideration on
  the
decision record is what action 1.05 asks for, and `EndorsementRoute` plus
`DecisionOutcome` is where it lands. The register that is separately mandatory
  is
the risk register, at action 1.10(a) "Identifies and documents organisational
risks", reinforced by the Victorian Clinical Governance Framework ("Documented
review of risks and mitigation actions are reported to the board at least
quarterly") and by Standing Direction 3.7.1's requirement for a risk management
framework consistent with AS ISO 31000:2018 whose components include "risk
registers and profiles". This family already satisfies that with `Risk`.

Two corrections to carry into any document that repeats this. NSQHS action 1.27
  is
"Evidence-based care", not new technology; the only new-technology hook in
  Standard
1 is 1.23(c), and its output is a scope-of-practice review for clinicians, which
would not bite on a SharePoint list. And **Australia has no DCB0129/DCB0160
analogue**: no mandatory clinical safety case report, no hazard log, no
  statutory
Clinical Safety Officer, and no Australian adoption of IEC 80001-1 or ISO
  81001-1
called up by any binding instrument. Do not cite one.

The design consequence is a narrowing, and a welcome one. Since no domain
  mandates
a per-change referenced report, `EndorsementRoute` should not pretend to index
one. It records that a named person in a named position endorsed on a date, and
cites a document only where one happens to exist.

### The one that is late: an ordinary `Action` row

The v1 design's own worked example for `Action` is
"Get guest access approved by 30 September" (the predecessor family's design
  document).
The chase is already modelled. `AssignedTo` is the person doing the chasing, not
the approver, because "one named person" is the column's whole doctrine
(`schema.dbml:354`: "'The team' is how actions quietly die") and an approver may
be a forum with no account.

**I decline to link the chase action to the paper.** `Action` is at 8
joins; a ninth trips the warning band, and the family's discipline is that "the
next governance idea has to argue for its column". `Action.AuthorisingDecision`
already exists and means something different, which is the decision an action
implements, not the decision an action is waiting on. Overloading it would make
both meanings unreadable.

The consequence, stated rather than hidden: **chase actions relate to the paper
  by
title and workstream, not by key, so reporting cannot join them.** Somebody
reading the register can see both rows and understand the relationship; a Power
  BI
model cannot compute "papers with an open chase action". If that number is ever
wanted, it is the argument for the ninth join on `Action`, and it should be
made then, with the count in hand.

## The exact schema

### `schema.dbml`, `Table Decision`

One column, inserted after `Detail` and before `LiveDecisionTitle` (calculated
columns stay last):

```text
  // The route the paper took, written once when the decision is recorded.
  // Plain text rather than rich text: this is read back as evidence and
  // exported, and rich text exports as HTML. Nothing at save can check it,
  // because a multi-line column is a forbidden validation operand, so the
  // monthly check reads it on the Decision log.
  EndorsementRoute longtext [note: 'Who the paper went to before it was decided, one line each: the party, the named person and their position, the date, and whether they agreed. Cite any assessment document by title rather than restating it. Blank when nobody outside the deciding forum saw it']
```

No index. It is never filtered, sorted or grouped on.

No `column_validation` and no `list_validation` branch. Both are impossible, not
merely omitted, and the reason belongs in a mapping comment.

No `form_visibility`. The field shows on both forms always. A rule keyed on
`Status` would be wrong in both directions: a `Proposed` paper may already have
been round the parties, and a `Noted` item may not have been anywhere.

### `mapping.yaml`, three edits

```yaml
# column_formatting, replacing the current line

  Involvement:
    Involvement: { style: pill, map: { Agree: warning, Consulted: low, Informed: neutral } }
```

`warning` rather than `severe` or `blocked`. The token vocabulary is exactly
`good, low, warning, severe, blocked, neutral, muted`
  (`analysis/styles.py:47-57`);
`warning` renders as `BgGold`. `Agree` is a party who can stop the work, which
  is
attention rather than failure, and the ordering gold, blue, grey reads down in
strength beside `Consulted: low` and `Informed: neutral`.

```yaml
# views.Involvement, the "Consultation load" view

    - title: "Consultation load"
      fields: [Title, Party, Activity, Involvement, Channel, Notes]
      where:
        - { field: Involvement, op: in, value: ["Agree", "Consulted"] }
      group_by: { field: Party, collapsed: false }
      sort:
        - { field: Title, direction: asc }
      widths:
        Title: 280
        Party: 180
        Activity: 240
        Involvement: 130
        Channel: 180
        Notes: 200
```

`Involvement` joins the rendered fields because the filter is no longer a
constant, and the reader now has to be able to tell an `Agree` row from a
`Consulted` one. Width 130 matches the two sibling views. `Involvement` is
already indexed (`schema.dbml`), so the `in` branch stays index-served and the
family's zero entries in `ACCEPTED_THRESHOLD_EXPOSURE` are preserved.

**Keep the view's title.** "Consultation load" is referenced in six committed
documents and was already created on a live site under that name
(`deploy-log-2026-08-28.txt:257`). Renaming it would provision a second view
beside the first for a cosmetic gain.

```yaml
# demo_items.Involvement, inserted before inv-privacy-comms

    - key: inv-privacy-signoff
      values:
        Title: "[DEMO] Sign-off that the privacy impact assessment is closed out"
        Activity: { demo_ref: act-approve-tenant-change }
        Party: { demo_ref: party-privacy }
        Involvement: "Agree"
        Channel: "Email"
        Notes: "Demo row. The one Agree in the register: the tenant change does not go to the provider until privacy has signed it off. A Consulted party can object; this one can stop it."
```

One row, not several. `Agree` should be rare in the demo data for the same
  reason
it should be rare in the register: if half the parties can veto, none of them
  can.

Two existing `Decision` demo rows should also gain an `EndorsementRoute`
value, so the field is seen filled and seen blank. One of the two should carry a
document reference in the OVIC shape, so the intended format is visible:

```text
Privacy - A. Chen, Privacy Officer - 2026-07-14 - endorsed. PIA "collaboration
uplift" v1.2, held in the Privacy team library.
Cyber - Health Service Cybersecurity Working Group - 2026-07-22 - endorsed subject
to conditional access being enabled first.
Executive Digital Committee - 2026-08-05 - approved.
```

### `formatting/programdecision-form-body.json`

```json
{
  "sections": [
    { "displayname": "The decision", "fields": ["Title", "Workstream", "SupersedesDecision", "DecisionDate", "DecidedBy"] },
    { "displayname": "Why", "fields": ["Detail"] },
    { "displayname": "Who it went to", "fields": ["EndorsementRoute"] }
  ]
}
```

The in-progress decision-route slice has not yet placed its own eight new
`Decision` columns in sections, so this file needs rewriting for that work
regardless. The section above is the part this proposal owns.

### `test/test_template_standard.py`, one line

`SECTION_BEATS[("<family>", "Decision")]` at lines 427 to 430
gains one entry:

```python
        "Who it went to": "Govern",
```

The resulting beats are `Identify, Assess, Govern`, which is an in-order
subsequence of `SECTION_ARC` (`test_template_standard.py:85`).

### Measured result

Built with these edits against the 12:10Z working tree, and compared with the
same tree unedited:

| Manifest line | Before | After |
| --- | --- | --- |
| Lists to provision | 9 | 9 |
| Non-lookup columns to create | 86 | **87** |
| Phase-2 lookup columns | 6 | 6 |
| Indexed columns | 51 | 51 |
| Views to provision | 42 | 42 |
| Formatted columns | 19 | 19 |
| Validation errors | 0 | 0 |
| Validation warnings | 3 | 3 |

The three warnings are identical before and after, and all three are
`form_columns_in_no_section` belonging to the in-progress decision-route slice.
`node --check --input-type=commonjs` passes on `deploy.js.txt`,
  `rollback.js.txt`
and `assess.js.txt`. The join distribution is unchanged at
`{2: 1, 3: 1, 4: 1, 5: 2, 8: 4}`, so the pinned `assert worst == 8`
(`test_template_standard.py:1710`) still holds and needs no deliberate re-pin
  from
this slice.

## The honest boundary

Built as above, this delivers a **route record and a named sign-off role**, and
nothing stronger.

It records which parties must agree before a standing activity proceeds, in a
  form
the quarterly review can group by party and see the load of. It records, per
paper, which parties the paper actually went to, who in each of them was the
  named
person, in what position, when, and whether they agreed. It keeps that record in
the same row as the decision itself, under the same permissions, the same
  version
history and the same no-delete treatment, so it survives the argument it exists
  to
close.

What it cannot deliver is **sign-off assurance**.

It cannot prove that a paper went to every party the standing route says must
agree, because that comparison is between a text field on `Decision` and a
set of rows on `Involvement`, and SharePoint validation formulas resolve
operands only against columns of the same list. That is measured, not assumed: a
field naming another list yields `condition_field_not_rendered`, and a lookup
reaching one yields `condition_lookup_unsupported_by_target`.

It cannot require the route to be filled at all, because `longtext` is a
  forbidden
validation operand, in the same class and for the same documented reason as
`ClosureNote` (`mapping.yaml:1224-1231`).

It cannot prove that the named person in a route line is the person who actually
holds that role, because the route is text, there is no membership list, and
person-to-party exists only through `Stakeholder.Contact`.

It cannot prove that a route line was written by the party it names, or that it
was not edited afterwards. `AppendOnly` is `False` on every Note column in this
codebase (`generators/jsgen.py:883`). The evidence that a line was not rewritten
is list version history, which is a reconstruction rather than a stamp.

It cannot verify that a cited assessment document exists, is current, or says
  what
the line says it says. The reference is text, and the document lives elsewhere.

It cannot show, at any moment, where a paper currently is. That is the
  deliberate
choice at the top of this document, not an accident of the platform, and the
design should say so in those words rather than leave it to be discovered.

It cannot show that the other health services approved a shared-tenancy change,
and should not try. Their approvals are the operator's records or the joint
  body's.

Every one of those is a reporting reconciliation or a human check on a named
  view,
not a rule. The moment the field is described as evidence that the required
approvals were obtained, it is making an assurance claim the platform cannot
  back.
What it is evidence of is narrower and still worth having: that on this date,
  the
person who recorded this decision stated in the register that the paper had been
to these parties, and that statement has not been quietly changed since. Against
NSQHS action 1.05, which asks that the organisation "considers the safety and
quality of health care for patients in its business decision-making", that is
enough. Against a claim of completed multi-party sign-off, it is not.

**The named human checks this creates.** Two, both on views that already exist:

- Monthly, on *Decision log*: any decision whose activity has `Agree` parties,
  and
  whose `EndorsementRoute` is blank. Nothing enforces this and nothing can.
- Quarterly, on *Consultation load*: any party appearing as `Agree` on more than
  a
  handful of activities. A party who can veto everything is a bottleneck that
  the
  register can now see, which is the whole reason for widening the view's
  filter.

## What was rejected, and why

### Option 1: SharePoint Approvals (Dataverse-backed flow). Rejected

The brief states that the program "already treats Dataverse-backed SharePoint
Approvals as a named dependency for an approval flow." **That is not the case,
measured.** A repo-wide search returns exactly one occurrence of "Dataverse", at
`analysis/limits.py:180-186`, and it says the opposite, warning that a
Dataverse formula limit was once wrongly believed to apply to SharePoint. Every
occurrence of "Approvals" in this family is the grouped view title "Decisions
  and
approvals". The four phase-2 Power Automate flows are declared "now, while no
  flow
exists" (`mapping.yaml:39-51`) and none of them is an approval flow. Adopting
Approvals would be introducing a new dependency, not inheriting one.

That alone would not be fatal. Five other things are, and they compound:

1. **It contradicts the project's headline promise.** `README.md:6` promises "no
   tenant admin rights, no premium licence, and nothing installed on the
  target",
   repeated at `website/docs/intro.md:13` and `pyproject.toml:4`. The Approvals
   connector is Standard, but the approval records live in Dataverse tables
   (`msdyn_flow_approval`, `msdyn_flow_approvalrequest`,
   `msdyn_flow_approvalresponse`) and reading them requires the Dataverse
   connector, which is Premium.
2. **The list side shows latest state only.** Whatever the flow writes back to
  the
   list item is a single current value. The per-approver trail, which is the
  thing
   case 2 actually needs, stays in Dataverse.
3. **There is no stable key linking an approval to the list item.** The link is
  a
   URL string in the approval's details, which cannot be joined on and breaks if
   the site is renamed.
4. **The trail is invisible to non-participants.** An approval is visible to its
   requester and its assigned approvers. The chair, the auditor and the next
   programme manager are none of those.
5. **The record is deletable by a third party.** Approval history is on
   Microsoft's documented manual deletion path for data subject requests, so a
   departing approver's request can compel destruction of the evidence. A
  register
   whose retention is decided by the people it records is not a register.

The failure mode is the one this repository was built to avoid: it would work in
  a
demo, and the evidence would not be there at the audit.

### Option 2: a "sign-off" child list mirroring the escalation-events list

  Rejected.

The premise needs correcting first. The escalation-events list was proposed at
the predecessor family's design review and **rejected** at
the predecessor family's design document in favour of a high-water-mark column,
  with a
named trigger and a reserved name. There is no escalation-events list to mirror.
The precedent it sets is the opposite of building one.

On its merits, a `SignOff` list is the honest way to model per-approver
state, and it fails on three counts.

**It is the tenth list, and there is no enforced ceiling, only a discipline with
  a
bar.** `NOT_YET_UPLIFTED` is empty (`test_template_standard.py:81`), so a tenth
list must satisfy every sweep: views with exactly one default, a form header and
body, demo rows exercising every view and every formatted column, arc-named
sections with a `SECTION_BEATS` entry, widths on the scale, an entity note with
room for the provenance marker, an entity name unique across every shipped
  family, an
index for every filtered view, a permissions block granting the reader group
  Read
and the administrators group Full Control, a `reporting-joins.md` row per
  lookup,
a workflow guide under `40-adopt/workflows/`, an extra manual attachments-off
  step
at go-live, and a deliberate re-pin of the join survey. The mapping cost is
  small.
The prose cost is roughly two dozen sites where "nine lists" is written down.

**It does not solve the problem it is built for.** A sign-off row needs a lookup
to the paper and a lookup or person for the approver. That is two joins on the
  new
list, which is affordable. What is not affordable is the reciprocal: to ask
  "does
this paper have all its sign-offs" you need to compare rows on one list against
rows on another at save time, and there is no mechanism. Measured: person,
lookup, multi-value, `longtext`, `richtext`, `hyperlink` and calculated operands
are all refused in validation formulas, and a field naming another list is
  refused
as not rendered. The list would hold the data and enforce nothing, which is
exactly what one text column does, at a tenth of the cost.

**It re-splits a layer the design deliberately joined.** `Involvement` is
the standing layer: one row per party per activity, permanent, reviewed
  quarterly.
Per-paper sign-off rows are the delivery layer. Putting instance rows into
`Involvement` would break the "Consultation load" count, which counts
standing relationships and would start counting events. Putting them in a new
  list
means two lists that both answer "who has to agree", differing only in tense.

`Involvement` has the most headroom in the family at 4 joins of 12, no
validation, no form visibility and one line of formatting. It is the cheapest
surface to extend, and that is a reason to add `Agree` to it, not a reason to
clone it.

### Option 3 as stated: standing `Agree` plus a `Detail` note - rejected in half

The standing half is right and is already landing. The `Detail` half is not.

`Detail` is `richtext`, and its note is specific about its job: "Context, the
options considered, and who disagreed. Enough that nobody reopens it in six
months." The sibling review's ruling on conflicts of interest extended `Detail`
  to
carry declarations and abstentions as well
(the decision-route review). Adding the
endorsement route makes it a fourth unrelated obligation on one free-text box,
  in
a format that exports as HTML, with no structure a reader can rely on. The
predictable outcome is that it is written for the first three decisions and then
stops.

The distinction that separates the two rulings is the one the review itself
  drew:
a conflict declaration is board machinery being mirrored proportionately onto a
programme register where it does not strictly apply, whereas the endorsement
  route
is the thing the programme manager is actually being asked for. Something asked
for weekly gets a field. Something mirrored by convention gets a sentence in an
existing note.

**The trigger for folding it back.** If, at two consecutive quarterly reviews,
`EndorsementRoute` is blank on more than half of the decisions whose activity
  has
`Agree` parties, the field is not being written and the honest move is to delete
it and put the sentence in `Detail`. A field nobody fills is worse than no
  field,
because a reader assumes a blank means "went nowhere" rather than "nobody typed
it".

### A fourth option, considered and rejected: three named endorsement fields

The obvious refinement is one column per domain, `PrivacyEndorsement`,
`CyberEndorsement`, `ClinicalEndorsement`, each a short text or a date. It is
tempting because it is filterable, and it fails for three reasons.

It costs three columns rather than one on a list that is already at 8 joins, and
two of the three would be blank on most rows, which is the rejected pattern
squarely and without the no-view escape, because a filterable column exists to
  be
put in a view. It hard-codes three approver domains into the schema, when the
actual route varies by paper and this family's own doctrine is that party
vocabulary lives in `Stakeholder` rather than in column names. And it asserts
  more
than the evidence supports: as established above, none of the three domains
mandates a per-change artefact for a Victorian public health service, so three
named fields would imply a three-gate process that no instrument requires and
  the
service may not run.

## Deferring the tenth list, properly

Following the predecessor family's design document, which is this family's
  worked
example of deferring a list.

**Reserved name: `{prefix}SignOff`.** `SignOff` and `Approval` should both
be checked against
`test_no_two_templates_declare_the_same_entity_name`
(`test_template_standard.py:2158`) before either is committed to, the way
`Escalation` was found already claimed.

**Trigger, countable and on a report:** a quarter in which more than a handful
  of
decisions record three or more distinct parties in `EndorsementRoute`, or any
quarter in which somebody needs the count of papers awaiting a specific party.
Both are read off the *Decision log* view by the person doing the quarterly
review, which is the point of writing them down.

The rule the escalation deferral establishes, and the reason this trigger is
phrased in counts, is stated at the predecessor family's design document: "'When
somebody asks twice' was v1's trigger and it is not one, because nobody counts.
  A
measure that goes stale twice is on a report."

## Migration and document edits

Nothing here is a breaking change. `EndorsementRoute` is a new nullable column,
and `Agree` is an append to a Choice member list, which reconciles in place.

**Deploy behaviour on an existing site.** The PREPARE phase unseals
  declared-seal
fields for the run and the PROTECTION phase re-seals them, so `seal_columns:
  true`
does not block either change. The `Choices` patch is a narrow MERGE with
  readback.
No existing item value changes, and no existing value is removed, which matters
because nothing in the deploy templates migrates stored values when a choice
member disappears.

**Code and configuration:**

1. `10-design/schema.dbml`: add `EndorsementRoute` to `Decision` with the
   comment block above. No index.
2. `20-configure/mapping.yaml:409`: add `Agree: warning` to the `Involvement`
  pill
   map.
3. `20-configure/mapping.yaml:696`: widen the "Consultation load" filter to
   `op: in, value: ["Agree", "Consulted"]`, add `Involvement` to `fields` and
   `Involvement: 130` to `widths`, and amend the view's comment so it says the
   view now detects both kinds of load.
4. `20-configure/mapping.yaml`: add the `inv-privacy-signoff` demo row, and add
   `EndorsementRoute` values to two existing `Decision` demo rows.
5. `20-configure/mapping.yaml:1332`: the demo-data summary comment says "six
   involvements". It becomes seven.
6. `20-configure/mapping.yaml:1596`: the `inv-privacy-comms` note says "Three of
   these six rows consult the same party". It becomes four of these seven.
7. `20-configure/mapping.yaml`: add a comment beside `list_validation` recording
   that "a decision whose activity has Agree parties carries an endorsement
  route"
   is not declarable, because `longtext` is a refused validation operand and the
   comparison is cross-list twice over. This matters because the same wall is
   already documented twice in this file and a third instance without a note
  reads
   as an oversight.
8. `20-configure/formatting/programdecision-form-body.json`: add the "Who it
  went
   to" section.
9. `test/test_template_standard.py:427-430`: add `"Who it went to": "Govern"` to
   `SECTION_BEATS`.

**Documents:**

1. `40-adopt/workflows/record-a-decision.md`: add the step that writes the
  route,
    with the line format spelled out and one worked example. This is the only
    place a user will read the format, so it is the edit that decides whether
  the
    field gets filled.
2. `40-adopt/staff-guide.md`: at line 145 and in the view table at line 397,
    "Consultation load" now shows both `Agree` and `Consulted` rows. In the
    "Recording a decision" section at line 241, name the new field and say when
  it
    is blank. Add `Agree` to whatever the guide says about involvement kinds.
3. `50-govern/governance.md`: at step 6 of the quarterly review (line 87), the
    overload detector now covers `Agree`. Add the two human checks named above
  to
    the control table in the form the existing four unenforceable controls take.
    Add a records-classification line for the new field. State that version
    history, not the field, is what shows a route line was not rewritten. Cite
    NSQHS action 1.05 as what the field satisfies, and correct any claim that
    VPDSS applies: PDP Act s 84(2)(d), (e) and (f) exclude a public hospital, a
    public health service and a multi-purpose service from Part 4, and VAGO says
    so in terms. The obligations that do bind are HPP 4.1 of the Health Records
    Act, NSQHS accreditation, and the *Policy and Funding Guidelines* cyber
    attestation regime. Do not assert a mandatory PIA: OVIC says conducting one
    "is not mandatory under Victorian privacy law".
4. `50-govern/reporting-joins.md`: no change. `EndorsementRoute` is not a join,
    which is worth one sentence in the file so the next reader does not go
  looking
    for it.
5. `README.md:110`: the `Involvement` view description mentions
    "Consulted rows grouped by party" and needs updating.
6. `30-deploy/deploy.md:116-118`: the shipped-manifest paragraph currently
  reads
    "9 lists, 75 non-lookup columns, 2 phase-2 lookup columns, 38 indexed
  columns,
    39 views, 19 formatted columns, and 0 validation errors and 0 validation
    warnings". **It is already stale by a wide margin in the working tree**,
  which
    now builds 86 non-lookup columns, 6 phase-2 lookup columns, 51 indexed
    columns, 42 views and 3 warnings. With this slice it becomes 87 non-lookup
    columns. Re-read the numbers from a fresh build rather than editing them by
    arithmetic, and do not let this slice be blamed for the drift it did not
    cause.
7. `30-deploy/deploy.md:134`: the demo-data paragraph mentions six involvements
    and *Consultation load*.
8. `20-configure/release.yaml`: bump, per the family's usual practice.

**Outside this slice, but blocking a green build.** The in-progress
  decision-route
work still owes demo rows exercising `Decision.Status` (currently the one
failing test), and form-body sections for the eleven columns now reported by
`form_columns_in_no_section` across `Activity`, `Action` and
`Decision`. Land those before or alongside this, or the slice will look
like it broke the build.

## Sources

Repository evidence is cited inline by file and line against the working tree at
2026-08-28 12:10Z. External sources below. Where a source could not be retrieved
directly it is marked, because this repository's own rule is that an unverified
claim is worse than a missing one.

### Multi-party approval, health and shared services

- Queensland Health, *Enterprise Information, Communications and Technology
  (ICT)
  Governance* Health Service Directive QH-HSD-064 v4.0 (28 January 2026), issued
  under s 47 *Hospital and Health Boards Act 2011*. The endorsement log, the
  15-working-day consultation period, and the majority test.
  <https://www.health.qld.gov.au/system-governance/policies-standards/health-service-directives/enterprise-information,-communications-and-technology-ict-governance>
- Department of Health (Vic), *Rural Public Health Care Agencies ICT Alliance
  Policy* (May 2026). Compulsory membership, Executive Committee authority, 75
  per
  cent vote. The underlying Joint Venture Agreement is unpublished and was not
  obtained.
  <https://www.health.vic.gov.au/publications/rural-public-health-care-agencies-ict-alliance-policy>
- Department of Health (Vic), *Policy and Funding Guidelines 2025-26*. The
  Digital
  Health Branch approval where scope impacts another health service; the $1m ICT
  project assurance threshold; the cyber strategy, mandated controls and VMIA
  attestation obligations; mandatory NSQHS accreditation.
  <https://www.health.vic.gov.au/policy-and-funding-guidelines>
- Public Record Office Victoria, *Managing Records in Microsoft 365: A guide for
  Victorian public offices*. The multi-tenant "VicGov" arrangement and the
  entitlement to be kept informed.
  <https://prov.vic.gov.au/sites/default/files/files/documents/managing_records_microsoft365_guideline.pdf>
- Public Record Office Victoria, shared platforms and tenancies guidance.
  "Delegation does not remove accountability."
  <https://prov.vic.gov.au/recordkeeping-government/a-z-topics/sharedplatforms>
- Cenitex and Public Record Office Victoria, joint statement on data retention
  in
  the Cenitex shared Microsoft 365 tenancy. Per-agency approval groups and the
  Shared Tenancy Working Group. **Retrieved at one remove: prov.vic.gov.au
  returns
  HTTP 403 to automated fetches.**
  <https://prov.vic.gov.au/about-us/our-blog/joint-statement-prov-cenitex>

- Victorian Auditor-General's Office, *Cenitex: Meeting Customer Needs for ICT
  Shared Services*. MoU per customer; brokering common agreement between
  customers
  with differing priorities; Stakeholder Advisory Committee attendance at 54 per
  cent.
  <https://www.audit.vic.gov.au/report/cenitex-meeting-customer-needs-ict-shared-services>
- ANAO, *Auditor-General Report No. 25 of 2016-17, The Shared Services Centre*.
  One board agrees changes to the services catalogue on behalf of all clients,
  and
  the audit finding that not all significant changes were referred to it.
  <https://www.anao.gov.au/work/performance-audit/the-shared-services-centre>

### Deemed approval

- *Intergovernmental Agreement for the Australian Consumer Law*, clauses 2 and
  13-19. The 35-day vote, "taken to have voted in favour", and unanimity
  reserved
  for amending the agreement itself.
  <https://consumerlaw.gov.au/sites/consumer/files/2015/06/acl_iga.pdf>
- *Planning Act 2016* (Qld), ss 29(8), 58 and 64. Deemed agreement, "Effect of
  no
  response", and the deemed approval notice with its second clock.
  <https://www.legislation.qld.gov.au/view/html/inforce/current/act-2016-025>
- *Environmental Planning and Assessment Act 1979* (NSW), s 8.11. Silence deemed
  a
  refusal.
  <https://legislation.nsw.gov.au/view/html/inforce/current/act-1979-203>
- OAIC, *FOI Guidelines* Part 3, on advising a consulted State that no response
  will be assumed to mean no objection.
  <https://www.oaic.gov.au/freedom-of-information/foi-guidelines>
- NSW Government ICT Agreement, clauses 8.2(f) and 14.3(f), and a published
  executed agreement in which both deeming sentences were amended out.
  <https://www.infrastructure.nsw.gov.au/media/yuxbtmnz/managed-services-provider-ict-agreement.pdf>
  and <https://www.info.buy.nsw.gov.au/resources/micta-icta>
- *National Health Reform Agreement Addendum 2026-2031*, clauses 45 and 46.
  Amendment "with the agreement of all Parties".
  <https://federalfinancialrelations.gov.au/agreements/national-health-reform-agreement>
- National Cabinet Terms of Reference (September 2024), clauses 31-34. Three
  days
  out of session, and escalation rather than deeming where unanimity is not
  reached.
  <https://federation.gov.au/national-cabinet>

### Privacy, cyber, clinical

- *Privacy and Data Protection Act 2014* (Vic) s 84(2), excluding public
hospitals, public health services and multi-purpose services from Part 4 and
therefore from the VPDSS; s 3, excluding health information from "personal
  information".
  <https://www.legislation.vic.gov.au/in-force/acts/privacy-and-data-protection-act-2014>

- Victorian Auditor-General's Office, *Security of Patients' Hospital Data*.
  "Under section 84 of the PDPA, health services do not need to comply with the
  VPDSS or its reporting obligations."
  <https://www.audit.vic.gov.au/report/security-patients-hospital-data>
- *Health Records Act 2001* (Vic), Schedule 1, HPP 4.1. Full-text scan of the
  authorised version returns zero occurrences of "impact assessment".
  <https://www.legislation.vic.gov.au/in-force/acts/health-records-act-2001>
- OVIC, privacy impact assessment guidance. "Although conducting a PIA is not
  mandatory under Victorian privacy law"; the register as "a good idea"; the
  enterprise risk register alternative.
  <https://ovic.vic.gov.au/privacy/resources-for-organisations/privacy-impact-assessment/>
- OVIC, *Privacy Impact Assessment Template*, Part 4. The endorsement table with
  columns Name, Position, Signature, Date, and the document-information block.
  <https://ovic.vic.gov.au/wp-content/uploads/2021/04/Privacy-Impact-Assessment-Template.docx>
- *Privacy (Australian Government Agencies - Governance) APP Code 2017*, ss 12,
  14
  and 15. Mandatory PIA, joint PIA with each agency retaining a copy, and the
  published register. Binds Commonwealth agencies only.
  <https://www.legislation.gov.au/F2017L01396>
- ACSQHC, *National Safety and Quality Health Service Standards*, 2nd edition.
  Action 1.05 (safety and quality considered in business decision-making),
  1.10(a)
  (identifies and documents organisational risks), 1.23(c) (scope of practice on
  new technology). Action 1.27 is "Evidence-based care", not new technology.
  <https://www.safetyandquality.gov.au/standards/nsqhs-standards>
- ACSQHC, *2026 National Model for Clinical Governance*, foundation 5. "A risk
  management plan is used to assess and mitigate risks before introducing
  digital
  tools and technologies ... and implementation of the risk management plan is
  monitored."
  <https://www.safetyandquality.gov.au/clinical-topics/clinical-governance/2026-national-model>
- Safer Care Victoria, *Delivering high-quality care: Victorian Clinical
  Governance
  Framework* (August 2024). Risk registries, reported to the board at least
  quarterly.
  <https://www.safercare.vic.gov.au/sites/default/files/2024-08/Victorian%20Clinical%20Governance%20Framework.pdf>
- Australian Signals Directorate, *Information Security Manual*. "An
  organisation
  is not required as a matter of law to comply with the ISM"; the authorisation
  package.
  <https://www.cyber.gov.au/resources-business-and-government/essential-cyber-security/ism>
- *Health Services Act 1988* (Vic) s 65S(2), the board duty the decision route
  already cites.
  <https://www.legislation.vic.gov.au/in-force/acts/health-services-act-1988>

Explicitly not found, after targeted search, and therefore not relied on: any
Australian mandatory clinical safety case report, hazard log or Clinical Safety
Officer role (no DCB0129/DCB0160 analogue); any Australian adoption of IEC
  80001-1
  or ISO 81001-1 called up by a binding instrument; any Victorian requirement
  for a
PIA or for a per-change security assessment artefact; and any published
  Australian
shared-ICT arrangement using deemed assent between peer agencies.

### Method and platform

- Bain & Company, RAPID decision-making tool. The `Agree` role and its veto.
  <https://www.bain.com/insights/rapid-tool-to-clarify-decision-accountability/>
- AXELOS, *Change Enablement: ITIL 4 Practice Guide* (2020), sections 2.4.2 and
  4.1.2. Change authority, and CABs as bottlenecks.
  <https://www.axelos.com/resource-hub/practice/change-enablement-itil-4-practice-guide>
- Queensland Cabinet Handbook, consultation requirements and the Consultation
  Addendum.
  <https://www.premiers.qld.gov.au/publications/categories/policies-and-codes/handbooks/cabinet-handbook>
- Microsoft Learn, Power Automate approvals and the Dataverse tables behind
  them.
  <https://learn.microsoft.com/en-us/power-automate/modern-approvals>
- Microsoft Learn, connector licensing. Approvals is Standard; Dataverse is
  Premium.
  <https://learn.microsoft.com/en-us/power-platform/admin/powerapps-flow-licensing-faq>
- Microsoft Learn, responding to data subject requests, listing approval history
  among the data requiring manual deletion.
  <https://learn.microsoft.com/en-us/power-platform/admin/powerapps-gdpr-dsr-guide>
- Microsoft Learn, SharePoint column formatting and list validation, the
  documented basis for refusing multi-line and person operands.
  <https://learn.microsoft.com/en-us/sharepoint/dev/declarative-customization/column-formatting>
