# Research ethics register — governance

## The boundary, before anything else

**No participant data goes into these lists. At any grain.**

The sector guide's first boundary — *nothing patient-identifiable goes into a
SharePoint list* — is easy to respect on a research register and easy to
erode, because the erosion is reasonable-sounding. The strict reading is the
one this template takes, and it is worth stating in words rather than leaving
implied:

- **No names, no identifiers, no clinical detail.** Obvious, and not the risk.
- **No recruitment, screening or consent counts — not even totals.** This is
  the one people argue about. "Twelve recruited at this site" is not
  identifiable, and it is also the first column; the second is "which twelve",
  and the third is a spreadsheet nobody sanctioned. Recruitment numbers belong
  in the clinical trial management system or the study file, which have the
  controls for them. Nothing in this register needs them: the register's job
  is *what was approved, by whom, until when, and what is owed*.
- **The reports themselves are not held here.** A progress report contains
  exactly the participant-level content this list must not. `Report URL` links
  where it is filed. Same stance as `credentialing-register`: the register
  indexes, the records system holds.
- **`Participant Involvement` is a property of the study design**, not of any
  person. Its members are categories of design — whether the project touches
  people at all, and how — and it is there because it is one of the things
  that decides which review pathway a project takes.

If a proposed new column would hold something about participants rather than
about the project, it does not belong here. That is the test.

## Ownership

| Role | Held by | Accountable for |
|---|---|---|
| Site authorisation | *(Chief Executive, or the delegate named in your instrument of delegation)* | Authorising a project for this site, and withdrawing that authorisation |
| Research governance officer | *(named role)* | The site-specific assessment, the register's accuracy, both sweeps |
| RG Research Governance | The maintaining group | Recording decisions the same week they arrive |
| Site investigator | — | Their project's rows being true; telling the office when anything changes |
| Principal investigator | — | The ethics application and the reports, wherever they sit |

The register records decisions; it never substitutes for the process. A row
whose authorisation has no reference and no date is a data-entry error, not
an authorisation.

## Decision authority (edit to your framework)

| Decision | Made by |
|---|---|
| Ethics approval, and its conditions | The external HREC. Never recorded here as anything but a transcription of their letter |
| Whether a quality or evaluation activity needs ethics review | Per your service's process for quality assurance and evaluation activities, recorded as `EthicsPathway` = *Quality assurance or evaluation - no ethics review* with the decision date in `Ethics Decision Date` |
| Site authorisation, and its withdrawal | Chief Executive or delegate, on the RGO's assessment |
| Suspension of a project at this site | The authority above; register updated the same day, `SiteAuthorisationStatus` = *Suspended* |

## The two sweeps

Both are monthly, both are named duties, and both exist because the register
**cannot compute them**. A SharePoint calculated column may not reference
`[Today]`, so nothing here derives urgency; the views and the cell colours are
live, and a person closes the loop.

**The expiry sweep.** Work *Approvals expiring* (anything inside 90 days) to
a decision each month: an extension amendment lodged, or a project closed. On
the day an approval passes its expiry, move `EthicsStatus` to *Expired*. That
is what makes **Site Readiness** say *Site authorised - ethics not cleared* —
in blocked red — for a project whose local paperwork still says yes. Until
somebody moves it, the readiness column is stale and says so nowhere.

**The reporting sweep.** Work *Outstanding reports* and *Due in 60 days*. The
red rows at the top of the first are already late, and **continued ethics
approval is contingent on the annual report** — the consequence of missing it
is not a reminder, it is the approval lapsing.

## Escalation

**A project running without site authorisation.** `ProjectStage` = *Underway*
with `SiteAuthorisationStatus` anything but *Authorised* is the one state this
register washes an entire row for. The governance officer contacts the site
investigator the same day; whether the project pauses is the Chief Executive's
or delegate's call, made through your research governance process — recorded
here, decided there. Do not resolve it by editing the stage.

**A safety event, protocol deviation or breach.** Goes to the reviewing
committee *and* to the local research governance officer, per your service's
procedure — the two are separate obligations and the second is the one that
gets forgotten. Record both in the report row's Notes.

## What is enforced at save, and what stays a governance check

Eight rules refuse a save. Everything else on this page is a discipline, and
the difference matters: when somebody asks *how did the service know this
project was authorised on that date*, "the system would not have let us" is
only an answer for the rows below.

| Rule | Where it lives | Why there |
|---|---|---|
| A submission, ethics decision or site authorisation cannot be dated in the future | **Enforced at save**, on the column (three rules on Project, one each on Amendment and ProgressReport) | Each reads only its own column, so each keeps its own message. A forward-dated decision makes Days to Ethics Decision negative and drops the project out of the queue it belongs in |
| **A project cannot be site-authorised unless ethics is cleared** | **Enforced at save**, on the list | The domain rule: authorisation is given against evidence of ethics approval. *Ethics review not required* counts as clearance, deliberately — refusing it would push adopters into recording a fake approval for a quality activity that correctly never went to a committee |
| An approved amendment needs a decision date | **Enforced at save**, on the list | That date is what the local clearance and the implementation are counted from |
| A report marked Submitted or Acknowledged needs a submitted date | **Enforced at save**, on the list | A claim with no date behind it cannot be checked by anyone |
| That `Approval Conditions` carries the committee's **verbatim wording** | **Governance check** | Rich text, and SharePoint validation formulas cannot reference a multi-line column at all. There is no formula to write. The form's own help text carries the instruction instead |
| That `Summary`, `Change Summary` and `Governance Notes` say anything useful | **Governance check** | Same reason |
| That a project has a **Site Investigator** before it is authorised | **Governance check** | Validation formulas cannot reference a person column at all. The *Approved, not authorised* view is where a blank one is caught |
| That `Ethics Status` is moved to **Expired** when the approval lapses | **Governance check** — the expiry sweep | Nothing can compute it; `[Today]` is refused in a calculated column |
| That conditions marked **Met** actually were | **Governance check** | Unenforceable in principle. *Conditions outstanding* is where it gets looked at |

## Data-quality rules

1. Both gates are recorded from the document, not from memory. An
   authorisation with no reference and no date has not been evidenced.
2. `AuthorisedBy` names a **role**, never a person. The individual changes;
   the delegation does not.
3. `ReviewingHREC` is written the same way every time. It is the closest
   thing this register has to a lookup and it is free text on purpose — an
   external committee is not a row anybody maintains.
4. Completed and discontinued projects are never deleted. The register's
   value is that it can still answer *what was approved here, by whom, and
   when* years later; that is also the question an audit asks.
5. A project's rows are updated in the week the decision arrives, not at
   report time.

## Where the regulatory claims come from

Every claim these documents make is one of these. They are here rather than
in the prose so a research governance officer can check them, and because the
one thing worse than no clause number is a wrong one.

| Claim | Source |
|---|---|
| Ethics approval and site authorisation are separate; the RGO assesses the SSA and the Chief Executive or delegate authorises; evidence of HREC approval is required before the site can authorise; both are needed before a project starts at a site | [RCH Research Governance — Governance only (SSA)](https://www.rch.org.au/ethics/new-applications/Governance_only_%E2%80%93_SSA/); [Sydney Health Partners, *Guide to Ethics and Governance Processes in NSW PHOs*](https://sydneyhealthpartners.org.au/wp-content/uploads/2025/09/SHP-Guide-to-Ethics-and-Governance-Processes-in-NSW-PHOs.pdf) |
| Lodging the SSA alongside the ethics application avoids delay | Same two sources |
| Progress reports go to the reviewing committee **at least annually**, and continued approval is contingent on them | [SLHD RPA post-approval guidelines](https://www.slhd.nsw.gov.au/rpa/research/postapproval.html) — *"reports on the progress of all approved studies must be submitted to the Committee at least annually"* |
| The report **due date** is set locally, not nationally | [RMH progress and final reports](https://www.thermh.org.au/research/office-for-research/post-approval-project-management/progress-and-final-reports) uses a fixed 31 March; other schemes use the approval anniversary. This is why the register stores a date per report rather than deriving one from a cadence |
| Safety events and breaches go to the **local research governance officer**, not only to the committee | [SLHD RPA post-approval guidelines](https://www.slhd.nsw.gov.au/rpa/research/postapproval.html) |
| **Negligible risk** = no foreseeable risk of harm or discomfort, at worst inconvenience. **Low risk** = the only foreseeable risk is discomfort. Lower-risk projects may take a review pathway other than the full committee | National Statement **Chapter 2.1**, as applied in the [NSW OHMR low and negligible risk review guideline](https://www.seslhd.health.nsw.gov.au/sites/default/files/groups/Research%20Website/Ethics%20Forms/OHMR%20LNR%20Guideline%20v1.1.pdf) and [SESLHD's summary](https://www.seslhd.health.nsw.gov.au/services-clinics/directory/research-home/ethics/low-risk-and-negligible-risk-research) |
| Not every quality-improvement or evaluation activity needs ethics review, and an organisation is expected to have a process for deciding | [NHMRC, *Ethical Considerations in Quality Assurance and Evaluation Activities* (2014)](https://www.nhmrc.gov.au/about-us/publications/ethical-considerations-quality-assurance-and-evaluation-activities) |
| A single ethical review is accepted across all states and territories for multi-centre research in public health organisations — which is why a service with no committee of its own can use somebody else's | [National Mutual Acceptance (SA Health)](https://www.sahealth.sa.gov.au/wps/wcm/connect/public+content/sa+health+internet/about+us/health+and+medical+research/research+ethics/national+mutual+acceptance); [Victorian NMA fact sheet](https://www.clinicaltrialsandresearch.vic.gov.au/national-mutual-acceptance) |

**Which edition of the National Statement.** The current one is the
**National Statement on Ethical Conduct in Human Research (2025)**, in effect
**from 23 June 2026**, superseding the 2023 edition
([NHMRC](https://www.nhmrc.gov.au/about-us/publications/national-statement-ethical-conduct-human-research-2025)).
Chapter 2.1 is the only paragraph number cited anywhere in this template, and
deliberately: Section 5's internal numbering was revised in 2023 and Section
4's in 2025, so a register that quotes a five-part number at a research
governance officer is one edition away from being wrong. Everything else here
is cited by what it says, not by where it sits.

**Nothing here states a fee, a form name, a turnaround time or a reporting
interval as a national rule**, because none of them is one. Where the template
needs an interval it stores a date you supply.

## Privacy

- Project metadata only. See the boundary at the top of this page; it is the
  load-bearing part of this document.
- The register does hold **staff professional information** — who is
  investigating what — and the conditions a committee attached to somebody's
  project. Neither is sensitive, both are visible to every site member by
  default, and that default is a deliberate operational choice: *may this
  start here* is a question ward managers, department heads and student
  supervisors all have to answer.
- If your context requires restriction, scope the site membership and record
  the decision here. Do not solve it by hiding columns — a column hidden in
  the form designer is not a permission, and this repository's own
  documentation is explicit that such a change is neither detected nor
  repaired.
- Investigators may see their own rows at any time. They should — the row is
  about their project.

## Lifecycle

Retention per your research governance and records schedule, which is long:
approval and authorisation records typically outlive the project by many
years, and a coronial or audit question can arrive later still. Export before
decommission; never run `rollback.js.txt` against real rows.
