# Research ethics register (single list): governance

## The boundary, before anything else

**No participant data goes into this list. At any grain.**

The healthcare sector guide's first boundary, *nothing patient-identifiable
goes into a SharePoint list*, is easy to respect on a research register and
easy to erode, because the erosion is reasonable-sounding. The strict reading
is the one this template takes, and it is worth stating in words rather than
leaving implied:

- **No names, no identifiers, no clinical detail.** Obvious, and not the risk.
- **No recruitment, screening or consent counts, not even totals.** This is
  the one people argue about. "Twelve recruited at this site" is not
  identifiable, and it is also the first column; the second is "which
  twelve", and the third is a spreadsheet nobody sanctioned. Recruitment
  numbers belong in the clinical trial management system or the study file,
  which have the controls for them. Nothing in this register needs them: its
  job is *what was approved, by whom, until when, and what is owed*.
- **The reports themselves are not held here.** A progress report contains
  exactly the participant-level content this list must not. Same stance as
  `credentialing-register`: the register indexes, the records system holds.
- **`Participant Involvement` is a property of the study design**, not of any
  person. Its members are categories of design (whether the project touches
  people at all, and how), and it is here because it is one of the things
  that decides which review pathway a project takes.

If a proposed new column would hold something about participants rather than
about the project, it does not belong here. That is the test.

## The shape of this register, and when it is the wrong one

This is the **single-list** research ethics register: one row per project,
with amendments and reports collapsed onto that row rather than given lists
of their own. That is a deliberate trade, and a service should make it
knowingly.

**Why one list.** A SharePoint Lookup picker enumerates its whole target list
and there is no way to restrict what it offers: the field has no filtering
attribute, the calculated-column workaround is refused past 5,000 items, and
the target list's own default view filter is ignored by the picker. All three
were measured on a live tenant; the tool's `reference/mapping.md` documents
them. A project register is an **accumulator**, so in a three-list design the
amendment and progress-report forms would, by year three, offer a picker full
of long-closed projects with the live one buried in it. That is not the
5,000-item threshold (5 to 30 projects a year never approaches it), and it
has no fix inside a list schema.

Filtering works everywhere in SharePoint *except* a lookup picker. Removing
the child lists turns the accumulation problem into one SharePoint solves
well: a default view filtered to live projects. **Project Stage** and the
**Live projects** view are that answer, and the mitigation depends on
both of them.

**What the trade costs.** No per-amendment and no per-report rows, so:

- The register cannot answer *which projects filed late in 2025*, or report
  on reporting timeliness across a portfolio.
- Two simultaneous in-flight amendments are not representable. The row holds
  the latest amendment's reference, status and date; a second overwrites the
  first and survives only in Governance Notes and version history, which is
  why versioning is set to 200 major versions rather than the library's usual
  fifty.
- There is no per-report link, only *the next one is due* and *the last one
  went*.

**Build the multi-list shape instead if** you run many concurrent projects
with frequent amendments, or you have your own research office with a
portfolio-level reporting obligation. That shape is a project list with an
amendment list and a progress-report list joined to it by Lookups, and it
answers the portfolio questions this one cannot. If you take it, take the
picker problem knowingly: curate the parent list so the picker stays short,
or build the picker outside a list schema with an SPFx form customizer.
Nothing in `mapping.yaml` can filter a lookup, and this template will not
pretend otherwise.

## Ownership

| Role | Held by | Accountable for |
| --- | --- | --- |
| Site authorisation | *(Chief Executive, or the delegate named in your instrument of delegation)* | Authorising a project for this site, and withdrawing that authorisation |
| Research governance officer | *(named role)* | The site-specific assessment, the register's accuracy, both sweeps |
| RG Research Governance | The maintaining group | Recording decisions the same week they arrive; keeping Governance Notes |
| Site investigator | n/a | Their project's row being true; telling the office when anything changes |
| Principal investigator | n/a | The ethics application and the reports, wherever they sit |

The register records decisions; it never substitutes for the process. A row
whose authorisation has no reference and no date is a data-entry error, not
an authorisation.

## Decision authority (edit to your framework)

| Decision | Made by |
| --- | --- |
| Ethics approval, and its conditions | The partner HREC. Never recorded here as anything but a transcription of their letter |
| Whether a quality or evaluation activity needs ethics review | Per your service's process for quality assurance and evaluation activities, recorded as `EthicsPathway` = *Quality assurance or evaluation - no ethics review* with the decision date in `Ethics Decision Date` |
| Site authorisation, and its withdrawal | Chief Executive or delegate, on the research governance officer's assessment |
| Suspension of a project at this site | The authority above; register updated the same day, `SiteAuthorisationStatus` = *Suspended* |

## The two sweeps

Both are monthly, both are named duties, and both exist because the register
**cannot compute them**. A SharePoint calculated column may not reference
`[Today]` (the tool refuses such a formula at build time), so nothing here
derives urgency. The views and the cell colours are live; a person closes the
loop. This is also why "report overdue" is a **view filter** in this template
and never a calculated column.

**The expiry sweep.** Open *Live projects* and **click the *Ethics Approval
Expiry* header to sort ascending** before you work it. That sort is not the
saved one (the view is stored sorted by title), and the overdue colouring
marks the lapsed and lapsing rows red without moving them, so on a register
of any size the ones you are looking for are scattered down the page until
you sort. Then work it to a decision each month: an extension amendment
lodged, or the project closed. On the day an approval passes its
expiry, move `EthicsStatus` to *Expired*. That is what makes
**Site Readiness** say *Site authorised - ethics not cleared*, in
blocked red, for a project whose local paperwork still says yes. Until
somebody moves it, the readiness column is stale and says so nowhere.

**The reporting sweep.** Work *Reports due soon*. The red rows at the top are
already late, and continued ethics approval is contingent on the progress
report. The consequence of missing it is not a reminder, it is the approval
lapsing. Check `Last Report Submitted` before chasing: a due date in the past
with a later submission behind it is a date nobody rolled, not a report
nobody wrote.

## Escalation

**A project running without site authorisation.** `ProjectStage` = *Underway*
or *Closed to recruitment*, with `SiteAuthorisationStatus` anything but
*Authorised*, is the one state this register washes an entire row for. Both
started stages count: a project only reaches *Closed to recruitment* by having
been *Underway*, so the recruiting has already happened, and the project is
still live and still in the default view. The governance officer contacts the
site investigator the same day; whether the project pauses is the Chief
Executive's or delegate's call, made through your research governance
process: recorded here, decided there. Do not resolve it by editing the
stage; closing recruitment does not clear it either.

**A safety event, protocol deviation or breach.** Goes to the reviewing
committee *and* to the local research governance officer, per your service's
procedure: the two are separate obligations and the second is the one that
gets forgotten, and the timeframes are short. Record both in Governance
Notes, dated.

**A project past five amendments.** The amendment data bar reads full. That
is not a rule, it is a prompt: a protocol that has moved five times is worth
a conversation about whether the approved project and the running one are
still the same thing.

## What is enforced at save, and what stays a governance check

Five rules refuse a save. Everything else on this page is a discipline, and
the difference matters: when somebody asks *how did the service know this
project was authorised on that date*, "the system would not have let us" is
only an answer for the rows below.

| Rule | Where it lives | Why there |
| --- | --- | --- |
| **A project cannot be site-authorised unless ethics is cleared, or once was** | **Enforced at save**, on the list | The domain rule: authorisation is given against evidence of ethics approval. *Ethics review not required* counts as clearance, deliberately. Refusing it would push adopters into recording a fake approval for a quality activity that correctly never went to a committee. *Expired* counts too, and for a different reason: a list validation formula sees only the row being saved, so it cannot tell an authorisation granted against a lapsed approval from an approval lapsing under one already granted. Refusing it would make the expiry sweep below impossible. What the rule still refuses are the statuses where clearance never existed |
| A submission, ethics decision or site authorisation cannot be dated in the future | **Enforced at save**, on each column (three rules) | Each reads only its own column, so each keeps its own message. A forward-dated authorisation says the site cleared a project it has not. All three dates are optional, and each rule carries a blank arm: the rule is *if there is a date it is not in the future*, not *there is a date* |
| Amendment count cannot be negative | **Enforced at save**, on the column | It is the only surviving trace of how many times the approved protocol has moved |
| That `Approval Conditions` carries the committee's **verbatim wording** | **Governance check** | Rich text, and SharePoint validation formulas cannot reference a multi-line column at all. There is no formula to write. The form's own help text carries the instruction instead |
| That `Summary` and `Governance Notes` say anything useful, and that Governance Notes is kept newest-first and dated | **Governance check** | Same reason. And the append discipline is a convention over an ordinary rich-text column: the deployer sets `AppendOnly` false on every multi-line column, so 200 versions of list history are the audit trail, not a platform guarantee |
| That a project has a **Site Investigator** before it is authorised | **Governance check** | Validation formulas cannot reference a person column at all. *Ethics cleared, not authorised* is where a blank one is caught |
| That `Ethics Status` is moved to **Expired** when the approval lapses | **Governance check**, the expiry sweep | Nothing can compute it; `[Today]` is refused in a calculated column |
| That conditions marked **Met** actually were | **Governance check** | Unenforceable in principle |
| That the latest-amendment columns are kept current, and superseded amendments moved into Governance Notes | **Governance check** | The cost of the single-list shape, paid here rather than hidden |

## Data-quality rules

1. Both gates are recorded from the document, not from memory. An
   authorisation with no reference and no date has not been evidenced.
2. `AuthorisedBy` names a **role**, never a person. The individual changes;
   the delegation does not.
3. `ReviewingHREC` is written the same way every time. It is the closest
   thing this register has to a lookup and it is free text on purpose. A
   partner committee is not a row anybody here maintains.
4. Completed and discontinued projects are never deleted. The register's
   value is that it can still answer *what was approved here, by whom, and
   when* years later; that is also the question an audit asks. The default
   view keeps them out of the way, which is why deletion is never necessary.
5. A project's row is updated in the week the decision arrives, not at report
   time. On a single-list register this matters more than usual: an
   overwritten amendment column is only recoverable from version history if
   the note beside it was written.

## Where the regulatory claims come from

Every regulatory claim these documents make is one of these, and each was
checked against the source cited before it was written down. They are
gathered here rather than left in the prose so a research governance officer
can check them, and because the one thing worse than no clause number is a
wrong one.

The sources are health-service statements of a national framework, and they
are from particular jurisdictions. **Check your own**. The framework is
national; the forms, the timeframes and the delegations are not.

| Claim | Source, and what it says |
| --- | --- |
| Ethics approval and site authorisation are **separate**; the research governance officer assesses the site-specific assessment and **recommends**, and the Chief Executive or delegate **authorises**; ethics approval is a prerequisite for authorisation; a project needs **both** before it starts at a site | [SLHD RPA, Site Specific Application (Governance)](https://www.slhd.nsw.gov.au/rpa/research/Governance.html): *"The RGO makes a recommendation to the Chief Executive (CE) or the CE's delegate who then authorises the research to be conducted at that site"*; *"Although SSAs can be submitted before ethics approval has been decided, they cannot be authorised until ethics approval for the study has been issued"* |
| Progress reports go to the reviewing committee **at least annually**, and continued approval is contingent on them | [SLHD RPA post-approval guidelines](https://www.slhd.nsw.gov.au/rpa/research/postapproval.html): *"reports on the progress of all approved studies must be submitted to the Committee at least annually"*, and approval runs *"subject to the receipt of satisfactory annual reports"* |
| The report **due date** is set locally, not nationally | [RMH progress and final reports](https://www.thermh.org.au/research/office-for-research/post-approval-project-management/progress-and-final-reports): *"Annual Progress Reports must be submitted by 31 March each year"*, a fixed institutional date set for that office's own reconciliation; other schemes use the approval anniversary. This is why the register stores a date you supply rather than deriving one from a cadence |
| Protocol deviations and suspected breaches go to the **local research governance officer**, not only to the committee or sponsor, and quickly | [SLHD RPA post-approval guidelines](https://www.slhd.nsw.gov.au/rpa/research/postapproval.html): a suspected breach is reported to the sponsor **and** the RGO within 72 hours of becoming aware of it |
| The National Statement sorts research risk into four profiles: **minimal** (*"No risk of harm or discomfort; potential for minor burden or inconvenience"*) and **low** (*"No risk of harm; risk of discomfort"*) are the lower-risk pair; **greater than low** (*"Risk of harm"*) and **high** (*"Risk of significant harm"*) are the higher-risk pair | National Statement (2025), Chapter 2.1, **Figure 1: Risk profiles of research**: read from the document itself, not from a summary of it |
| Research **greater than low risk must go to an HREC**; research of **no more than low risk may be reviewed under other processes**, and an institution may determine that some research is exempt from ethics review | National Statement (2025), *Purpose, scope and limits*: *"Research with a greater than low level of risk (as defined in Chapter 2.1) must be reviewed by a Human Research Ethics Committee (HREC). Research involving no more than low risk may be reviewed under other processes"* |
| **"Negligible risk" is not current National Statement vocabulary.** The 2025 edition uses *minimal* where earlier editions said *negligible*. The pathway member in this register is still named **LNR (low and negligible risk)**, because that is what the state review pathways, their application forms and their committees are still called, and an operator picks the pathway their committee's form names, not the one a national document names | The 2025 edition's Figure 1 carries no "negligible" category; state health services still publish LNR pathways and LNR application forms. If your partner committee has renamed its pathway, rename this Choice member to match its form |
| Not every quality-improvement or evaluation activity needs ethics review, and an organisation is expected to have a **process** for deciding | [NHMRC, *Ethical Considerations in Quality Assurance and Evaluation Activities* (2014)](https://www.nhmrc.gov.au/sites/default/files/documents/attachments/ethical-considerations-in-quality-assurance-and-evaluation-activites.pdf): guidance for identifying triggers for ethical review and for deciding the appropriate level of oversight |
| A single ethical review is accepted across jurisdictions for multi-centre research in publicly funded health services, which is why a service with no committee of its own can use somebody else's, while **site governance stays local** | [ACT Health, National Mutual Acceptance scheme](https://www.act.gov.au/health/conducting-health-research/ethics-and-governance/nma-scheme): *"a national agreement for mutual acceptance of a single scientific and ethical review for multi-centre health and medical research conducted in publicly funded health services across all Australian states and territories"*, with local research governance processes still applying |

**No paragraph numbers are quoted anywhere in this template**, deliberately.
The National Statement's internal numbering has been revised more than once,
and a register that quotes a five-part number at a research governance officer
is one edition away from being wrong. The two exceptions above are a *chapter*
and a *figure*, coarse enough to survive a renumbering, and the figure is the
definition rather than a paraphrase of it. Everything else is cited by what it
says.

**Which edition of the National Statement.** The current one is the **National
Statement on Ethical Conduct in Human Research (2025)**, published by NHMRC
with the Australian Research Council and Universities Australia (NHMRC
publication reference E72D). That much is read from the document itself, and
so are the risk profiles above.

**The document carries no commencement date.** Its publication details give the
year and nothing finer, so the widely reported effective date of **23 June
2026**, superseding the 2023 edition, rests on
[NHMRC's own page for the edition](https://www.nhmrc.gov.au/about-us/publications/national-statement-ethical-conduct-human-research-2025)
and on secondary reporting, not on anything inside the PDF. Treat the edition
as established and the date as worth confirming, and note that your partner
committee's transition arrangements are its own to set, whatever the national
date says.

**Nothing here states a fee, a form name, a turnaround time or a reporting
interval as a national rule**, because none of them is one. Where the
template needs an interval it stores a date you supply.

## Privacy

- Project metadata only. See the boundary at the top of this page; the rest
  of this document depends on it.
- The register does hold **staff professional information** (who is
  investigating what) and the conditions a committee attached to somebody's
  project. Neither is health information about an identifiable person, which
  is the boundary this register is built around and the one it will not
  cross. Whether either should nonetheless be visible to every site member is
  **your** decision, not this template's, and `30-deploy/deploy.md` makes it a
  gate before first build. The default is read-wide, and the reason is
  operational: *may this start here* is a question ward managers, department
  heads and student supervisors all have to answer, and a register only the
  governance office can see is a register nobody consults.
- If your context requires restriction, scope the site membership and record
  the decision here. Do not solve it by hiding columns. A column hidden in
  the form designer is not a permission, and this repository's own
  documentation is explicit that such a change is neither detected nor
  repaired.
- Investigators may see their own rows at any time. They should. The row is
  about their project.

## Lifecycle

Retention per your research governance and records schedule, which is long:
approval and authorisation records typically outlive the project by many
years, and a coronial or audit question can arrive later still. On this
register the **version history is part of the record**, not an artefact of
it (it is where superseded amendments live), so an export must capture it.
Export before decommission; never run `rollback.js.txt` against real rows.
