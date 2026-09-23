# Seam register

*Theme: governance, risk & compliance.*

One register for finding what your organisation depends on its providers
for, where the joins are, and which of them nobody can describe. One row per
provider, one row per service, every fact behind a service as an evidence
row, every disagreement as a seam, and the files that back it all in one
library.

## Why

An organisation that gets its ICT, or any other service, from a
shared-services body, a managed service or a handful of vendors relies on
services and workarounds that nobody on either side can describe, verify or
document. Nobody can say what each provider supplies, what the organisation
runs itself, and where the joins are. This family finds those joins on
purpose, at a pace two people can sustain alongside their day jobs, and
produces something a decision-maker can read in one page.

Nothing is known until it is in a row with evidence against it. The
register's confidence rule has three values. **Assumed** means nobody has
told us. **Claimed** means one person or one document says so. **Verified**
means two independent sources agree, or system evidence shows it, and both
of us have read the evidence.

## The lists

| List | One row per | What it is for |
| --- | --- | --- |
| `SEAM_Provider` | Provider | Every organisation we depend on, once: its type, its tier, the role that manages the relationship, how to reach it and the agreement it works under. Retired, never deleted |
| `SEAM_Service` | Service or capability | The register. Which side runs it and which provider, who to call, who decides, where it runs, how confident we are. Roles, never names |
| `SEAM_Evidence` | Fact | What a source said, as close to verbatim as possible, and which side it came from. A service with no evidence rows is Assumed by definition |
| `SEAM_Seam` | Disagreement or gap | The product of the exercise. A type, a status, the evidence rows in conflict, and who will resolve it by when |
| `SEAM_DocumentRequest` | Document asked for | To ask, asked, received, refused or not found. Not found is a result and gets a row |
| `SEAM_Artefact` | File held | A document library: copies received, interview notes, ticket exports, invoice lines and emails, filed by kind in six folders and linked to the services they bear on. An evidence row and an interview row can pick a file from it by its Title, so every file gets one |
| `SEAM_Interview` | Conversation | The same eight questions every time, thirty minutes at most, so every conversation is comparable |
| `SEAM_Incident` | Ticket or remembered outage | Twelve months of exported tickets. Who closed a ticket is the strongest single signal of who really runs the service |
| `SEAM_WeeklyUpdate` | Week | Five lines every Friday: rows verified, seams found, what is blocked, what is next, one surprise |

## Side and provider

A service, an incident, a document ask and an interview each say two things
about who is involved. The **side** is a fixed choice: *Us*, *Provider*,
*Third party*, *Shared* or *Unknown*. The **provider** is a lookup into
`SEAM_Provider` that names which one, and appears on the form once the side
is *Provider*, *Third party* or *Shared*.

Each form shows a field once the row has reached it: the resolution once a
seam is resolved, the eight answers once an interview is completed. A field
hidden again by a later change keeps its old value, and the row still
saves. Views and reporting filter on status and side, so the old value
does not surface.

The side carries everything a fixed value has to: the save rule that a
claimed service names a team, the colours, the seam map's grouping and the
two-source rule on evidence. SharePoint validation cannot read a lookup, so
none of that could hang on the provider column. The provider column carries
what a fixed value cannot: any number of providers, each with its own
details, and a view of one provider's whole footprint. Evidence rows and
files carry the side alone, because the two-source rule compares sides.

## The seam map is a view

The one-page picture is a query, not a drawing. **Seam map** on the service
list takes every first-pass row, groups it by which side runs it, and
colours it by confidence. Us and Provider are the two columns of the
one-pager; Shared straddles them and Unknown is the gutter between. The
provider column beside each row says which provider. **By provider** cuts
the same register by provider instead. Open seams sit beside it on the seam
list, oldest first.

**By resolver** on the incident list draws the same picture from data
rather than interviews: twelve months of tickets grouped by which side
closed them. The differences between the two pictures are the seams worth
talking about first.

## Views

| List | View | Purpose |
| --- | --- | --- |
| Provider | Active providers | Every provider in use, by name. The default |
| Provider | By tier | Every provider grouped by tier |
| Provider | Agreements ending | Providers in use with an agreement end date, soonest first |
| Provider | Retired | Providers no longer used, kept because rows still point at them |
| Service | Seam map | First-pass rows grouped by which side runs them, coloured by confidence. The default |
| Service | By provider | Rows run by a provider, a third party or shared, grouped by which provider |
| Service | By support provider | Rows supported by a provider, a third party or shared, grouped by which one, including rows another side runs |
| Service | Provider not named | Rows whose run-by or support side owes a provider and names none |
| Service | By area | Every row grouped by first-pass area |
| Service | Assumed | First-pass rows nobody has told us about yet |
| Service | Single person | Rows only one named individual can operate or repair, with the Saturday-night answer |
| Service | Undocumented | Rows whose documentation is not asked, not found or not seen |
| Service | Failures | Rows with a dated failure, most recent first |
| Service | Backlog | Rows sent to the second pass |
| Evidence | By service | Every fact grouped by the row it supports. The default |
| Evidence | Contradicting | Evidence that disagrees with another row for the same service |
| Evidence | By source side | Grouped by which side the fact came from |
| Evidence | Recent | Newest evidence first |
| Seam | Open seams | Open, confirmed and escalated seams, oldest first. The default |
| Seam | Escalated | Seams handed to a decision-maker, by the date agreed |
| Seam | By type | Unresolved seams grouped by type |
| Seam | Resolved | How each seam closed |
| DocumentRequest | To ask and waiting | Asks not yet answered, by due date. The default |
| DocumentRequest | Received | Copies held, with what each is silent on |
| DocumentRequest | Refused or not found | The results that are themselves findings |
| DocumentRequest | By holder | Every ask grouped by which side holds the document |
| DocumentRequest | Provider not named | Asks whose holder side owes a provider and names none |
| Artefact | Folder View | The six folders |
| Artefact | All artefacts | Every file across folders, recently modified first. The default |
| Artefact | By source side | Every file sorted by which side produced it, newest first within each |
| Artefact | Answers an ask | Files that answer a document request |
| Interview | Booked | Conversations still to have, soonest first. The default |
| Interview | Completed | Conversations held, with their follow-ups |
| Interview | By side | Every conversation grouped by side |
| Interview | Not held | Declined and cancelled, which are evidence too |
| Interview | Provider not named | Conversations whose side owes a provider and names none |
| Incident | By resolver | Twelve months of tickets grouped by which side closed them. The default |
| Incident | By service | Tickets grouped by the service row assigned |
| Incident | Remembered outages | The ones nobody logged |
| Incident | Unassigned | Tickets not yet matched to a service row |
| Incident | Provider not named | Tickets whose resolver side owes a provider and names none |
| WeeklyUpdate | Weekly log | Week 1 to 6. The default |
| WeeklyUpdate | Latest first | The most recent five lines |

## Save rules

The rules SharePoint holds:

- Naming a side that runs or supports a service needs the team or role
  beside it. Unknown may stay blank.
- A single-person service needs the out-of-hours answer.
- Escalating a seam names who will resolve it and by when. Resolving it
  needs the resolved date.
- Once asked, a document has an asked-on date and a due date. Received,
  refused and not found each need the date the answer came back. A received
  agreement, schedule or attestation says who signed it, or *Unsigned*.
- A completed interview has its duration, at most thirty minutes.
- A remembered outage says who remembered it.
- No recorded date is in the future. Week is 1 to 6, and the weekly counts
  are not negative.

Naming the provider is not a save rule, because a formula cannot read a
lookup; **Provider not named**, on each of the four lists with a provider
column, finds the rows that owe one. The two-source Verified
rule is a governance check too: a formula cannot count evidence rows on
another list. See [governance](50-govern/governance.md) for the
checks the register cannot make on its own.

## Customisation points

- The providers themselves are rows, not configuration. Add them in
  `SEAM_Provider` before the first interview.
- The first-pass areas, in the `service_area` enum.
- The provider types and tiers, in the `provider_type` and `provider_tier`
  enums.
- The six artefact folders, in `entities.Artefact.folders` and the
  `artefact_type` enum together.
- The eight interview questions, in the Interview column notes and display
  names. Keep the count: the script is what makes conversations comparable.
- The six-week cap on `WeekNo`, if the exercise runs longer.

Build with `--seed` for demonstration rows that return something in every
view and render every formatted column; [deployment](30-deploy/deploy.md)
lists them. Nothing in them names a real organisation or person.
