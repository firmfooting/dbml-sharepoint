# Deploying seam register (administrator)

Shared procedure: [solution deployment](../../README.md), using
`seam-register`. Eight lists and one document library, all prefixed
`SEAM_`. Assess the site, review the generated manifest, paste the deploy
script, then verify the lists and the library.

## Before you build

- [ ] Check the provider types and tiers in the DBML `provider_type` and
      `provider_tier` enums. The providers themselves are rows in
      **SEAM_Provider**, added after the deploy and before the first
      interview; nothing in the build names one.
- [ ] Check the first-pass areas in the DBML `service_area` enum. The
      shipped six are identity and access, backup, retention and records,
      infrastructure and devices, business applications, the M365 tenant,
      and other.
- [ ] Check the six artefact folders in `entities.Artefact.folders` and the
      `artefact_type` enum. Add a folder and a type together.
- [ ] Decide who is in **SEAM Discovery Team** (the two people running the
      exercise, who can add, edit and delete) and **SEAM Contributors** (the
      people offered rows to correct, who can edit but not delete). Site
      members read. Site Visitors get no access, because exact
      reconciliation grants only what the mapping lists; add
      `associated_visitor_group` to `list_permissions` if they should read.
- [ ] Agree the site's sharing settings. The mapping uses exact permission
      reconciliation; inspect the generated manifest before deploying.
- [ ] Plan browser-based use of the library. Microsoft's
      [OneDrive read-only guidance](https://learn.microsoft.com/en-us/troubleshoot/sharepoint/lists-and-libraries/files-open-as-read-only-and-cannot-check-in-or-out)
      describes the sync restriction for libraries with validation.

## Build and demonstrate

```bash
dbml-sharepoint build \
  --schema 10-design/schema.dbml \
  --mapping 20-configure/mapping.yaml \
  --release 20-configure/release.yaml \
  --site-url https://yourtenant.sharepoint.com/sites/your-site \
  --time-zone Region/City \
  --site-role default \
  --seed \
  --out ./build
```

Paste `assess.js.txt`, review `deploy-manifest.md`, then paste
`deploy.js.txt`. For a demonstration, paste `demo-data.js.txt` afterwards.
It creates four providers (one retired), seven services across the five
side values, seven evidence
rows including a contradicting pair, four seams in every status, five
document asks in every status, seven files across the six folders, four
interviews, five incidents and two weekly updates. Nothing in it names a
real organisation or person. The seeded links name the seeded files but
point at an example host, so they are placeholders rather than working
links; a real row links the file where it was uploaded.

**Artefact file** on an evidence row and **Notes file** on an interview row
are lookups into the library, shown by each file's **Title**. Measured on a
live site on 2026-09-18 (`test/manual/library-lookup-write-probe.js`, four
runs): the form's save path and the deploy's seed write both set a
Title-bound lookup to a file, the value reads back and renders in views,
and the picker lists titled files only, which is why every seeded file
carries a Title and the staff guide asks for one on upload. Binding to the
file name instead was measured and refused: its picker lists every file,
and then the row cannot be read back. A calculated copy of the name was
refused at creation, so there is no binding that shows the name. Six
seeded evidence rows and the completed interview pick their seeded file;
the hyperlink columns beside them stay as the direct link.

Standard deployment logging is separate infrastructure; use the build's
`--no-sidecars` option if local logging sidecars are not wanted.

## Verification checklist

- [ ] The eight lists and the **SEAM_Artefact** library exist, and the
      library has the six folders: Documents, Interviews, Incidents,
      Invoices, System exports and Correspondence.
- [ ] Every view in the family README exists. **Seam map** is the default on
      the service list and groups by **Run by**; the demonstration rows land
      in four groups (Us, Provider, Shared and Unknown; no seeded first-pass
      service is run by a third party), with **Confidence** coloured and
      **Run by provider** naming the shared ICT service on the backup and
      virtual desktop rows.
- [ ] **By provider** groups the services by **Run by provider**: the
      shared ICT service runs two, the telephony managed service one, and
      the visitor badge row sits in the blank group because nobody has
      named its vendor. Rows we run, or nobody has claimed, are not in the
      view. **By support provider** puts the M365
      tenant row under the cloud platform although we run it. **Provider
      not named** on the service list shows the visitor badge and desk
      phones rows, each on a side that owes a provider nobody has named. The
      same view shows one row on each of the document request, interview
      and incident lists: the attestation ask, the declined interview and
      the slow-desktop ticket.
- [ ] On the provider list, **Active providers** is the default and shows
      three. **Agreements ending** shows two, the telephony service first.
      **Retired** shows the previous backup vendor, and its past
      **Agreement ends** date is not red because it is retired. A member of
      **SEAM Discovery Team** can edit a provider but not delete it.
- [ ] **By resolver** is the default on the incident list and groups by
      **Resolved by**. The unassigned demonstration ticket appears in
      **Unassigned**.
- [ ] Add a service. **Run by provider** is hidden while **Run by** is
      *Unknown*, and appears when it is set to *Provider*, *Third party* or
      *Shared*. Set *Provider* with no **Run by team** and the save rule
      refuses it. Set **Run by** to *Unknown* and it saves. Add a second
      service with the same **Title** and uniqueness refuses it.
- [ ] Tick **Single person** on a service with no **Out of hours call**. The
      save rule refuses it.
- [ ] Add a seam. **Raised on** fills with today. Set **Status** to
      *Escalated* without a **Resolve owner**. The save rule refuses it.
      Set *Resolved* without a **Resolved on** date. The save rule refuses
      that too, and **Resolved on** and **Resolution** appear only once the
      status is *Resolved*. Set a resolved seam back to *Open* and it saves,
      keeping the hidden date.
- [ ] On a seam, **Evidence in conflict** accepts more than one evidence
      row.
- [ ] Add a document ask. **Asked on** and **Due on** appear once the status
      leaves *To ask*, and the save rule refuses *Asked* without both, or
      without a **Holder** and a **Held by** other than *Unknown*. Set
      a received *Attestation* with no **Signed by** and the save rule
      refuses it.
      **Due on** turns red once it has passed and the status is still
      *Asked*, and stops once the status is *Received*, *Refused* or *Not
      found*. **Answered on** appears for those three, and the save rule
      refuses any of them without it.
- [ ] Upload a file into the library's Interviews folder. Its **Type**
      defaults to *Document copy*; set it to *Interview notes*. **Services**
      accepts more than one service row. It appears in **All artefacts** and
      **By source side**, and in **Answers an ask** only once **Request**
      is set.
- [ ] On the demonstration evidence rows, **Artefact file** shows the
      seeded file's Title on the six rows that link one, and the
      completed interview's **Notes file** shows the interview notes. Open a
      new evidence row: the **Artefact file** picker lists the seven seeded
      files by Title. Upload a file without typing a Title and it is not
      offered until it has one.
- [ ] Add an interview with **Status** *Booked* and a date next week. The
      eight questions and the follow-ups are hidden on the new form and
      appear once the status is *Completed*. Set *Completed* with the future
      date and the save rule refuses it. Enter 45 minutes and the duration
      rule refuses it. Set *Declined* instead: **Follow-ups** appears and
      the eight questions stay hidden.
- [ ] Add an incident with **Source** set to *Recalled outage* and no
      **Source detail**. The save rule refuses the row until it is filled.
      Add a second incident with an existing ticket reference as its
      **Title** and uniqueness refuses it.
      **Source detail** is on the form for a ticket export too, for the
      export it came from.
- [ ] Add a weekly update with **Week** set to 7. The save rule refuses it.
      Add a second row for a week that already has one, and uniqueness
      refuses it.
      Set **Rows verified** to -1 and the count rule refuses that too. All
      five lines are required; zero and *None* are answers.
- [ ] Sealed columns and list deletion protection are enabled. Verify with
      the generated verification script after the deploy.

These checks include rendered behaviour. A successful build or JSON readback
alone does not establish that a form or view works as intended.

## Manual adoption settings

The deploy creates the six folders; it does not set folder metadata
defaults. In Library settings, configure **Column default value settings**
so that a file uploaded into Interviews defaults its **Type** to *Interview
notes*, Incidents to *Incident export*, Invoices to *Invoice extract*,
System exports to *System export* and Correspondence to *Correspondence*,
then verify a test upload in each. These manual settings are not reconciled
by redeployment.

Apply the organisation's retention label if its records policy requires
one. Interview notes and correspondence about a provider are the kind of
record that policy usually covers.

Populate **SEAM Discovery Team** and **SEAM Contributors**. Remove the
synthetic demonstration rows and files before the first real interview.

## Enterprise reporting access

The deploy declares the `dbml Enterprise Readers` site group, shared with
every other family deployed to the site, and grants it `Read` on every list
in this family. The group starts empty only if no family has deployed to the
site yet; it gains a member when any family's build is run with
`--enterprise-reader <account>`, which enrols exactly that one account and
nothing else. `rollback.js.txt` does not remove it: rollback deletes lists,
not site groups or role assignments, so the group and any account enrolled
in it survive a rollback.

A later build that omits the flag does not put the group back to empty:
enrolment only runs when `--enterprise-reader` is given, so an account
enrolled by an earlier build, of this family or any other sharing the site,
keeps its membership and its `Read` grant on every list it was declared
against. Removing it is manual: clear it in Site permissions > Groups.

If the group already holds anyone other than that account, the deploy
**aborts before enrolling** and removes nobody. Before you clear anyone out,
check who it is: the group is shared by every family on this site, so the
unexpected member is most likely **another family's reporting account**, and
removing it silently breaks that family's reporting. Agree one reader
account for the site and rebuild with that address, or rebuild without the
flag. Only clear the group in Site permissions > Groups once you know
nothing else needs the account.
