# Opportunities register

*Theme: process digitisation & improvement — governance-light.*

A thin routing layer for business problems that a project discovers but is
not authorised or funded to fix. It captures the problem once, sends it to an
existing control or owner, and stops tracking when that destination accepts
it. One list: `OR_Opportunity`.

The template assumes strict information boundaries and established incident,
risk, complaints, privacy, project and delivery systems. It complements those
systems instead of becoming another place to manage the same work.

## The promise

This register must save more effort than it creates:

- a submitter gives four short facts plus one safety/privacy check;
- a steward chooses the shortest valid route, usually without a meeting;
- only genuinely uncertain or material opportunities receive a benefit
  assessment;
- existing incident, risk, complaints, privacy, project and delivery systems
  remain authoritative;
- executives see exceptions and decisions, not another detailed register.

It is not an incident or emergency channel, case record, enterprise risk
register, complaints system, business case, project backlog or delivery
tracker.

## Stop before capture

The first field is a mandatory stop gate. A submission cannot save when the
user selects **Urgent, sensitive or unsure — use routing guide first**.

Use the organisation's required pathway first for current or potential harm,
safety incidents, complaints or disclosure processes, privacy/cyber concerns,
legal or regulatory breaches, service interruptions and emergencies. Never
put personal identifiers, case-record content or sensitive employee, customer
or third-party detail in this list. If the project still needs to preserve a
wider improvement observation afterwards, record only a de-identified process
summary and the controlled-system reference. Local policy and law always win.

## Capture in about a minute

The New form requires only:

1. **Safety and privacy check** — confirms the required pathway has been used
   and the list is safe for a de-identified process observation.
2. **Problem or opportunity** — a specific one-line title.
3. **Problem Statement** — two to four plain-language sentences: what happens,
   who is affected and why it matters.
4. **Service or facility area** — the likely routing destination, using a
   localised choice set; **Not sure** is better than guessing.
5. **Source Project** — where the problem was encountered.

Three useful inputs remain optional: evidence/source link, project link and
why the project cannot own the work. A steward confirms the scope boundary
before the record leaves `Captured`. Created By is the default contact, so the
submitter does not re-enter their own name.

## Triage by the shortest path

`Triage Outcome` records one route:

| Route | What the steward does | Terminal status here |
| --- | --- | --- |
| Incident/safety, organisational risk, complaint/disclosure, privacy/cyber, or project issue/change | Confirm the required record exists; save only its safe identifier/link | `Transferred` |
| Direct hand-off to known owner | Obtain receiving-owner acceptance and record its work item | `Transferred` |
| Duplicate/already governed | Point to the existing record | `Duplicate` |
| Close after screening | Give a concise reason; do not manufacture a business case | `Not proceeding` |
| Assess here | Name an owner and one dated next action | `Assessing` |

Fast exits do not require benefit scoring, an effort estimate or a decision
pack. That is the main defence against governance tax.

Only `Assess here` continues through:

`Assessing` → `Awaiting decision` → one of:

- `Accepted` → `Transferred` after an existing destination accepts it;
- `Parked` with a real review date and trigger;
- `Not proceeding` with a short rationale.

Status and Triage Outcome are separate because one says where the record is
and the other says why it took that path. Stewards keep the pair coherent.

## Prioritisation without false assurance

Routine assessment uses:

`Priority Score = Benefit Potential × Time Criticality`

| Input | 1 | 2 | 3 | 4 |
| --- | ---: | ---: | ---: | ---: |
| Benefit Potential | Limited | Material | Major | System-wide |
| Time Criticality | Flexible | Within 12 months | Within 3 months | Time-sensitive |

| Score | Conversation cue |
| ---: | --- |
| 1–4 | Routine |
| 5–8 | Consider |
| 9–12 | Prioritise |
| 13–16 | Prompt decision |

This is not a risk or safety instrument. Selecting an existing safety/risk,
equity, service-continuity, executive or statutory override blanks the number
and displays **Use existing priority**. The organisation's authorised
framework then determines urgency.

## Friction budget

| Moment | Design target | Control |
| --- | --- | --- |
| Submit | About 60–90 seconds | Four facts + stop gate; links optional |
| Triage | Most records in under 3 minutes | Redirect, hand off, duplicate or close without assessment |
| Assess | Only where a real choice remains | Coarse value/time/effort; link detailed evidence |
| Decide | Existing authority, usually asynchronously | Only material or contested decisions reach a forum |
| Oversee | One exception digest | No new committee and no acceptance-rate target |

These are local operating targets, not service promises encoded in SharePoint.

## Access and privacy

- Ordinary Site Members and Site Owners receive no declared list grant.
- Named **OR Opportunity Submitters** can submit and read, but cannot edit or
  delete.
- Before adding submitters, an administrator must manually configure
  SharePoint item-level access to **read items created by the user**. The
  deployer cannot reconcile this setting, so it is a go-live gate with a
  two-account verification test.
- Attachments are disabled manually before go-live. Comments remain enabled as
  the low-friction clarification channel, under the same no-identifiers and
  no-sensitive-content rule as the form.
- A small **OR Opportunity Stewards** group can add/read/update every item but
  cannot delete records. Its custom level includes SharePoint `Manage Lists`
  because that permission is what bypasses read-own filtering; membership must
  therefore remain tightly controlled, with sealed columns and list-deletion
  protection retained.
- **dbml List Administrators** holds Full Control for controlled maintenance.
- Evidence stays in its existing controlled system; the register holds a link
  and de-identified summary.

The inability to safely combine submitter edit-own access with role-specific
workflow fields in a standard SharePoint form is intentional: submitters
clarify through comments and the steward applies material corrections to
governed fields.

## Presentation and form customisation

The register follows the same shared presentation pattern as the risk register:

- a live form header with a Fluent icon, record title, concise purpose, safety
  callout and process links;
- a sectioned body that follows the workflow and keeps calculated outputs in a
  final **System** section;
- conditional visibility that keeps steward, assessment, decision and hand-off
  fields out of the way until they are relevant;
- native SharePoint severity boxes, pills, icons, an in-view score bar and
  overdue-date treatments;
- one restrained row-level signal in **Decisions**, reserved for **Prompt
  decision** and **Use existing priority**; and
- intentional view widths and ordering so each queue can be worked without
  opening every item.

All styling uses the shared SharePoint semantic classes, Fluent icons and
tenant theme colours. There are no fixed brand colours to maintain.

## Five operational views

| View | One job |
| --- | --- |
| **Needs triage** *(default)* | Oldest untriaged submissions first |
| **Assessments** | Items deliberately commissioned for assessment |
| **Decisions** | Existing decision authorities, due-date first; calculated score bar plus tenant-theme emphasis for prompt/override rows |
| **Handoff and deferred** | Accepted transfers and genuinely dated deferrals |
| **Closed and redirected** | Proof of where work went or why it stopped |

The generated unfiltered **All Items** view is hidden from the modern view bar
and remains available for recovery and controlled reporting. There is no
Quick wins view: ease must not crowd out safety, equity or necessary structural
work.

## Why this design

Useful registers make ownership, routing, decisions and evidence visible
without asking people to duplicate authoritative records. This design therefore
captures the problem once, provides fast exits to existing controls, and asks
for more information only when a genuine priority or investment decision
remains.

The optional business-case and benefit fields retain the useful discipline
from [Australian Government business-case guidance](https://www.finance.gov.au/government/commonwealth-investment-framework/commonwealth-investments-toolkit/developing-business-case)
and [UK benefits-management guidance](https://www.gov.uk/government/publications/guide-for-effective-benefits-management-in-major-projects),
but only after triage decides that assessment is worth the effort.

## Work the folders in order

| Step | Folder | You |
| --- | --- | --- |
| 1 | `10-design/` | Replace Service Area and route choices with local language |
| 2 | `20-configure/` | Set access groups, process URLs, score definitions and views |
| 3 | `30-deploy/` | Build, deploy, set read-own access, and verify with two accounts |
| 4 | `40-adopt/` | Give submitters one minute of guidance; train stewards on routing |
| 5 | `50-govern/` | Embed the queue in existing governance and enforce the stop rules |

Build with `--seed` to add nine de-identified `[DEMO]` records covering
minimal capture, incident/safety-system redirect, direct hand-off, assessment
with an equity override, decision, acceptance, parking, screening closure and
duplicate closure.
