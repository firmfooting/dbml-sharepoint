# Opportunities register — governance without governance tax

## Governing principle

This register earns its place only when it reduces total organisational work.
It is a **capture-and-route control**, not a new governance domain. Existing
clinical, risk, complaints, privacy, project, investment and delivery systems
retain their authority.

Use three tests for every field, meeting and report:

1. Does it route the item, support a real decision or preserve necessary
   evidence?
2. Is this fact already held somewhere authoritative?
3. Will a named person use it soon enough to justify collecting it?

If the answer is no, stop collecting or reporting it.

## Non-negotiable healthcare boundary

The register never receives patient-identifiable information, clinical-record
content or sensitive personnel detail. Current or potential harm, clinical
incidents, complaints/open disclosure, privacy/cyber matters, statutory
breaches, emergencies and service interruptions use the health service's
required pathway first.

The form enforces a stop gate, but a validation rule cannot recognise sensitive
prose. Stewards recheck every new item. If a submitter used the wrong channel:

1. initiate/confirm the mandatory process immediately;
2. restrict further circulation of the SharePoint item;
3. follow local privacy/records advice for any inappropriate content;
4. retain here only a de-identified process observation and controlled-system
   reference when there is a continuing improvement purpose.

The [NSQHS Clinical Governance Standard](https://www.safetyandquality.gov.au/national-standards/nsqhs-standards/clinical-governance-standard)
requires organisation-wide incident, risk and complaints systems. This list
points to those controls; it does not reproduce them.

## Minimal ownership model

| Role | Held by | Accountable for |
| --- | --- | --- |
| Register owner | Existing improvement, quality, operations or portfolio executive | Boundary, access, steward capacity, exception reporting and stop-doing review |
| OR Opportunity Stewards | A small named routing function | Safety recheck, route selection, concise records, decision coordination and verified hand-off |
| Submitter | Named project staff member | Four capture facts and safe/de-identified content |
| Opportunity Owner | Existing service/process owner | Assessment and hand-off only when `Assess here` is commissioned |
| Decision authority | Existing delegated person or forum | Material pursue, defer or stop decision |
| Receiving owner | Owner in the authoritative destination | Delivery and benefit realisation after transfer |

Do not create an Opportunities Committee. Add a short exception item to the
most relevant existing forum. Do not put every Opportunity Owner into the
Stewards group; a steward can record an asynchronously supplied assessment or
decision.

## Access model and manual control

Exact ACL reconciliation grants access only to:

- **OR Opportunity Submitters** — `OR Submit Only`;
- **OR Opportunity Stewards** — add/read/update every item without item-delete;
- **dbml List Administrators** — Full Control for controlled maintenance.

Associated Site Members and Site Owners receive no declared grant. Site
collection administrators may still possess platform-level authority; audit
that separately.

SharePoint states that people with permission to manage lists can read and edit
all items despite item-level filtering. `OR Steward No Delete` therefore
includes `ManageLists`, but deliberately omits `DeleteListItems`. `ManageLists`
also carries structural authority, so keep the steward group very small and
retain sealed columns, exact deployment reconciliation and list-deletion
protection. See Microsoft's [list introduction](https://support.microsoft.com/en-us/sharepoint/lists/get-started-with-sharepoint/introduction-to-lists)
and [permission-level reference](https://learn.microsoft.com/en-us/sharepoint/understanding-permission-levels).

Before real submitters are added, configure List settings → Advanced settings →
Item-level Permissions so submitters read only items they created. The deployer
cannot configure or assess this setting. The two-account isolation test in the
deployment guide is therefore a mandatory go-live and post-change control.
Disable attachments in the same Advanced settings pass. Keep list-item comments
enabled as the low-friction clarification channel. Comments inherit the item
audience and the same prohibition on identifying/sensitive content. A material
fact, route or decision is still recorded in the governed fields; comments are
conversation, not the authoritative decision record. Train users to cancel any
`@mention` prompt that offers to grant wider access; see Microsoft's
[list-comment guidance](https://support.microsoft.com/en-us/sharepoint/lists/add-and-reply-to-comments-in-list-items).

Submitters do not edit after save because a standard SharePoint form cannot
safely allow edit-own while protecting manager workflow fields by role. The
intake is intentionally small; stewards append material corrections and
versioning preserves them.

Review all three groups quarterly and after role changes. Do not use broad
project, hospital-wide or departmental groups as Submitters merely for
convenience.

## Triage contract

The default objective is a decision about **where the item belongs**, not a
decision about whether to fund a solution.

| Triage Outcome | Intended Status | Minimum evidence |
| --- | --- | --- |
| Clinical incident/safety, organisational risk, complaint/open disclosure, privacy/cyber, project issue/change | Transferred | Confirmed destination ID/link and Delivery Route |
| Direct hand-off to known owner | Transferred | Receiving owner acceptance, destination ID/link and route |
| Duplicate/already governed | Duplicate | Existing record ID/link |
| Close after screening | Not proceeding | Concise reason |
| Assess here | Assessing | Opportunity Owner and one dated Next Action |

Before leaving Captured, the steward also confirms the real project scope,
authority or funding boundary. Calling something out of scope without a real
boundary is not sufficient.

The SharePoint formula enforces that non-Captured items have a Triage Outcome
and scope boundary, but it deliberately stays below SharePoint's 32-condition
limit. It cannot enforce every Status/Triage Outcome pairing. The steward
checks the table above as a small human control rather than adding fields and
workarounds.

## Assessment is an exception

Commission `Assess here` only when no authoritative destination can accept the
problem without a real value, capacity or priority decision. Full assessment
is required for Awaiting decision, Accepted and Parked; it is not required for
redirects, direct hand-offs, duplicates or screening closure.

Assessment covers only:

- credible evidence and root cause, linked rather than copied;
- primary Benefit Type;
- Benefit Potential as reach: Limited, Material, Major or System-wide;
- Time Criticality as loss of opportunity value, not emergency severity;
- order-of-magnitude Effort Band;
- strategic/obligation alignment;
- one patient, consumer, equity or cultural-safety consideration;
- one proposed baseline-to-target measure;
- any existing-priority override.

Options, whole-of-life cost, clinical assurance, workforce consultation and
formal consumer partnership belong in the receiving improvement, risk,
business-case or change process when warranted.

## Score and hard overrides

For routine non-clinical ordering only:

`Priority Score = Benefit Potential (1–4) × Time Criticality (1–4)`

| Score | Cue |
| ---: | --- |
| 1–4 | Routine |
| 5–8 | Consider |
| 9–12 | Prioritise |
| 13–16 | Prompt decision |

The score does not measure clinical risk, consequence, equity, cultural safety,
service continuity, statutory duty or executive authority. When one applies,
choose the relevant Priority Override. The local score becomes blank and the
record displays **Use existing priority**. Record/link the authorised rating or
direction in the destination system; never invent a second risk matrix here.

Do not publish a Quick wins queue as an executive priority list. Low effort is
useful implementation information, not a reason to crowd out high-consequence
or structurally necessary work.

## Existing-authority decisions

Most redirects and direct hand-offs need no separate opportunity decision.
Where `Assess here` reaches a choice:

- use a person already delegated to commit the receiving service's capacity;
- prefer asynchronous approval when evidence and authority are clear;
- use an existing meeting only for material funding, cross-service trade-offs,
  safety/risk implications or contested authority;
- record a short decision/date/rationale and link the real business case;
- do not make the project board the organisational investment authority merely
  because it discovered the problem.

`Parked` is rare. It requires a review date and a specific event/evidence that
could change the decision. After two unchanged reviews, the existing decision
authority explicitly accepts another deferral or closes the item. Silent
roll-forward is prohibited.

## Hand-off contract

Transferred means this register stops. The steward checks:

1. the receiving record exists;
2. its owner has accepted responsibility;
3. the identifier/link is safe for this audience;
4. the receiving record can stand alone using linked authorised evidence.

Do not copy destination status, milestones or benefit updates back into this
list. End-to-end reporting follows the Destination Link under that system's
access controls.

## Cadence by exception

There is no fixed twice-weekly meeting or universal decision SLA.

- Required safety/privacy routes: follow the existing pathway immediately.
- Routine Needs triage: one steward clears it asynchronously at a locally
  realistic interval, suggested weekly as a starting point.
- Decisions: notify the named authority; table only unresolved material items
  in its next existing forum.
- Handoff and deferred: work overdue dates by exception, not as a standing
  read-through of every row.
- Project closure: link to any still-open record; do not re-enter its content.

If the steward cannot maintain the queue, pause intake or narrow eligible
projects. An unstaffed register is organisational theatre.

## Minimum reporting

The executive view is a short exception digest, ideally generated from the
existing operational views:

1. untriaged records older than the local expectation;
2. active records without an owner or with an overdue next action;
3. decisions requiring executive/delegated authority;
4. accepted work not yet received;
5. repeated cross-service themes that suggest a system problem.

Do not report every field, every item, acceptance rate, or meeting activity.
Measure median time to route/decision only when someone will act on it. Sample
quarterly whether submissions and triage still meet the friction budget; ask
submitters and stewards what can be removed. Retire views, fields and reports
that have no decision use.

This follows the Australian Commission's
[2026 National Model for Clinical Governance](https://www.safetyandquality.gov.au/clinical-topics/clinical-governance/2026-national-model),
which identifies excessive risk reporting and compliance-led data collection
as warning signs, and its
[practical implementation guide](https://www.safetyandquality.gov.au/clinical-topics/clinical-governance/2026-national-model-practical-guide-implementation),
which advises health services to integrate with existing mechanisms, avoid
unnecessary new structures and make governance simpler for the workforce.

## Enforcement boundary

SharePoint enforces:

- the safety stop-gate choice;
- real scope wording when supplied;
- Triage Outcome and scope boundary before leaving Captured;
- full assessment only at Awaiting decision, Accepted and Parked;
- dated next actions while the register actively owns work;
- decision, review, delivery-route and destination-reference gates;
- future-decision-date rejection;
- versioning, sealed columns, exact ACLs and deletion-resistant UI controls.

Humans verify sensitive content, correct routing, Status/Triage Outcome
coherence, owner/authority acceptance, narrative quality and destination
access. Person and multi-line fields cannot participate in SharePoint
validation formulas, and technology cannot manufacture authority or capacity.

## Records and decommissioning

Apply the health service records schedule to decision and routing records.
Export before decommissioning and never use `rollback.js.txt` against real rows.
Sealing and deletion protection prevent casual UI mistakes; they do not replace
authorised records-management decisions.
