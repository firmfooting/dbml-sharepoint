# Seam register: guide

## What this is

Two people, six weeks, one question: what do we depend on our providers
for, and where are the joins? Eight lists and a library hold the answer. Nothing
is known until it is a row in **SEAM_Service** with an evidence row against
it.

## Principles

**Facts about services, never about people.** A service row says who runs
a thing and who to call when it fails, in role terms. Names live in the
calendar. An interview that turns into a grievance gets a one-line note and
we move on.

**Three sources for every claim.** What we say, what the provider says, and
what a document or a system shows. Where two disagree, that is a seam and it
gets its own row rather than a quiet judgement call.

**Confidence has three values.** *Assumed* means nobody has told us.
*Claimed* means one person or one document says so. *Verified* means two
independent sources agree, or system evidence shows it. A row moves to
*Verified* only when both of us have read the evidence, and the register
cannot check that for you.

**Boundaries.** About thirty rows in the first pass, the rest in the
backlog. No designing, no recommending tools, no interview over thirty
minutes, no row without evidence.

## The weekly rhythm

**Monday, two hours.** Open **Seam map** and pick the week's rows. Book the
conversations as **SEAM_Interview** rows with **Status** *Booked*. Send the
document asks and record each as a **SEAM_DocumentRequest** row with
**Status** *Asked*, **Asked on** today and **Due on** five working days out.

**Midweek.** At most three thirty-minute interviews. Open the booked row,
set **Status** to *Completed*, and the eight questions appear. Type the
answers as close to verbatim as you can. Then transcribe: each answer that
names a service becomes a **SEAM_Evidence** row against that service, with
**Source** as the role, **Source side** as their side, and
**Evidence date** as the interview date. Upload your notes to the
library's Interviews folder, give the file a **Title** in its details pane,
and pick it in **Notes file** on the interview row and **Artefact file** on
each evidence row. The pickers list titled files only. Keep **Artefact
link** beside it.

**Friday, two hours.** Update the register. Move rows to *Verified* only
where two evidence rows from different sides agree. Raise a **SEAM_Seam**
row for every disagreement, with the evidence rows in conflict picked in
**Evidence in conflict**. Then write the five lines as a **SEAM_WeeklyUpdate**
row: rows verified, seams found, what is blocked, what is next, one
surprise.

## Recording a provider

Before the first interview, open **SEAM_Provider** and add every
organisation you already know you depend on: the shared-services body, any
managed service, the vendors whose support you call directly and the cloud
platforms you build on. **Provider** is the name everyone uses. Set
**Type**, and set **Tier** once you have a view of how much depends on it.
**Relationship owner** is the role here that manages it, not a name.
**Service desk contact** is how it is reached when something breaks. Link
the agreement if you hold it and date **Agreement ends**.

Add a provider whenever an interview names a new one. When one stops being
used, set **Status** to *Retired*. A provider cannot be deleted, because
services, incidents and interviews still point at it.

## Recording a service

Open **SEAM_Service** and add a row. **Title** is the name the people who
run it use, not a category. Set **Area**, and say in **Description** what it
does in two sentences a non-ICT reader can follow.

**Run by** and **Support from** start as *Unknown*. Each says which side:
*Us*, *Provider*, *Third party*, *Shared* or *Unknown*. Naming a side in
either needs the team or role beside it; the save rule holds you to that.
Once the side is *Provider*, *Third party* or *Shared*, **Run by provider**
or **Support provider** appears: pick the provider. The save rule cannot
check that one, so **Provider not named** lists the rows that still owe it.
**Decided by** is who can change it. **Hosting** is where it runs.
**Dependency** is what inside this service we cannot do without a
provider, stated plainly. Blank means none known, not none.

Tick **Single person** when only one named individual can operate or repair
it, and answer **Out of hours call**: if it failed on a Saturday night, who
gets the call? The save rule needs both together.

**Documentation** starts at *Not asked*. Move it to *None found*, *Exists,
not seen*, *Held* or *Verified* as the answer comes back, and put the
location in **Documentation link** once you hold a copy. Date the most
recent failure anyone can remember in **Last failure date** and say what
happened and how it was noticed.

Leave **Confidence** at *Assumed* until evidence says otherwise. Untick
**First pass** to send a row to the backlog without losing it.

## Recording evidence

Every fact traces to a **SEAM_Evidence** row. **Title** is the source and
the date in a few words. **Service** is the row it supports or contradicts.
**Type** says what kind of source it is; **Source** says who or what, as a
role for a person, a title for a document, an export date for data.
**Source side** is which organisation it came from, which the two-source
rule needs. **Statement** is what the source says, as close to verbatim as
possible, with no paraphrase that adds meaning. **Bears on** names the
service column the fact is about.

Tick **Contradicts** when this row disagrees with another evidence row for
the same service, and raise a seam.

## Raising a seam

A seam is a place two sources disagree or nobody answers. Open
**SEAM_Seam** and add a row. **Raised on** fills with today. Choose the
**Type**: no owner, disputed owner, disputed support, undocumented
dependency, single person, no evidence, or contradicts document. Write the
disagreement in one paragraph naming the sources by role, and pick the
evidence rows in conflict.

A seam stays *Open* until we and the provider agree the gap is real, which
is *Confirmed gap*, or it is handed to a decision-maker with a date, which
is *Escalated* and needs **Resolve owner** and **Resolve by**. **Resolve
by** turns red once it has passed. When a source of truth is found, set
*Resolved*, date it in **Resolved on** and say in **Resolution** how it
closed and what changed on the service row. A seam is never resolved by
quietly editing the service row.

## Asking for documents

Every document asked for gets a **SEAM_DocumentRequest** row, found or
not. Start at *To ask*. Move to *Asked* with **Asked on** and **Due on**;
the save rule needs both. When a copy arrives, set *Received*, date it,
upload the file to the library's Documents folder and set **Request** on the
file to this row. Say in **Summary** what it covers and what it is silent
on, and for an attestation or agreement, who signed it and when.

*Refused* and *Not found* are results. Record the date, who was asked, and
what they said, and raise a seam if the absence matters.

## Filing artefacts

**SEAM_Artefact** is the library. Upload a file into the folder that
matches its kind: a copy received into Documents, interview notes into
Interviews, a ticket export into Incidents, invoice lines into Invoices, a
console export into System exports, an email into Correspondence. Then
select the file, open its details pane, and type a **Title**: the pickers
on evidence and interview rows list titled files only. A Word, Excel or
PowerPoint file may arrive with a Title from its own document properties;
check it says what the file is. A PDF, an export or an email never brings
one. Uploading a new version of an Office file replaces the Title with
whatever the file carries, so check it again after a re-upload. Set
**Type** and **Source side**, date it, and pick the **Services** it bears
on. Say in **Summary** which section or line matters.

## Incidents

Ask for twelve months of tickets and service requests, grouped by category
and by who resolved them. Each becomes a **SEAM_Incident** row with the
ticket reference as its **Title**, **Resolved by** as the side that closed
it, **Resolving provider** as the provider where there is one, and
**Source** as *Ticket export*. Assign each to a service row as you
go; **Unassigned** shows the ones still to match.

Add the outages people remember with **Source** set to *Recalled outage*
and the role who remembered it in **Source detail**. The week no accounts
were created is the model entry.

**By resolver** is the second picture of the seam map, drawn from data
rather than interviews. Where it disagrees with **Seam map**, start there.

## Stop rules

No designing. No tools recommended. No business application beyond its one
question until the first pass is closed. No row without an evidence row. No
interview past thirty minutes. If the register passes forty first-pass rows,
stop adding and start verifying.
