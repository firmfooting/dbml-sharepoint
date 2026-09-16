# Digital innovation log: champions and digital team guide

The log is where an M365 ask goes so that it is answered once and built
once. Champions capture; the digital team routes, scores, decides and checks
adoption. Neither group can delete a row: an ask leaves as Routed,
Duplicate or Not now, and every reader can see why.

## Champions: capture in about a minute

Open `DI_Opportunity` -> **New**. The form shows the **What we heard**
fields and none of the digital team's, and you type nine things:

1. **Title**: the ask in one line, as the person said it. "Can Teams do our
   roster" is better than "Rostering solution".
2. **Problem Statement**: two to four sentences on what happens today, who
   is affected and why it matters.
3. **Service Area**: the service the ask came from. Choose *Not sure*
   rather than guessing.
4. **Team or unit**: the ward, team or unit you heard it in.
5. **Current Method**: how the work is done today.
6. **People Affected**: how many it touches, in four steps. This is the
   only sizing you are asked for.
7. **Heard at**: the workshop, floor walk, drop-in or meeting.
8. **Data Sensitivity**: would a solution touch patient, clinical workflow
   or sensitive staff data? *Not sure* is an honest answer and decides who
   reviews the ask; it does not decline it.
9. **Requested for**: the staff member who raised it. You are recorded as
   Created By.

Save. Status becomes Captured, Captured Date fills with today and the ask
appears in **Needs response**.

The New form hides the digital team's fields, but SharePoint does not stop
a champion opening any ask afterwards and editing them. The split between
champions and the digital team is a working rule, not a permission: correct
a capture, never a triage, and leave the scored fields to the Owner.

What never goes in: a patient, a clinical record, a named staff grievance.
Describe the process, not the person. Attachments are switched off by the
administrator after deployment; if there is a document, describe it or link
it from a place the reader is authorised to open.

What to say to the person who raised it: "It is logged, you will hear back
within a week, and you can see it in the log."

## Champions: what is not an ask

A fault, an access request or a how-do-I question is a helpdesk ticket
today, and the champion says so and points the person at the helpdesk. An
incident, a complaint, a privacy or cyber concern goes to its mandated
system first, per the header on the form.

If you are not sure, capture it. Triage routes it within the week and the
requester still gets a reply. A captured ask that turns out to be a ticket
costs a minute; an unanswered one costs the rollout its credibility.

## Digital team: triage in three piles

Read **Needs response** oldest first. For each ask pick one **Triage
Outcome** in under a minute:

| Pile | Triage Outcome | Then |
| --- | --- | --- |
| Route it out | Service request or fault - send to the helpdesk | Status Routed; Receiving reference is the ticket |
| Route it out | Already available - show and train | Status Routed; Receiving reference is the how-to or the session booked |
| Route it out | Process change - improvement register | Status Routed; Receiving reference is the improvement id |
| Route it out | Project-sized - project pipeline | Status Routed; Receiving reference is the pipeline id |
| Route it out | Incident, complaint, privacy or cyber - mandated system | Status Routed; Receiving reference is the record id |
| Close it | Duplicate - merge into the earlier ask | Status Duplicate; Receiving reference names the earlier ask |
| Close it | Not now | Status Not now; Decision Date, and Reopen trigger says what would change the answer |
| Keep it | Explore here | Status Exploring; name an Owner |

Set **Acknowledged Date** when the requester has been told, whichever pile
the ask went to. The seven-day *Acknowledge by* stops being red the moment
the ask leaves Captured, so leaving Captured without telling the requester
defeats the clock; tell them first.

The form refuses to leave Captured without a Triage Outcome and an
Acknowledged Date, refuses Routed and Duplicate without a Receiving
reference, and refuses Not now without a Decision Date and a Reopen trigger
of more than fifteen characters.

Only *Explore here* continues. Everything else is finished once the
requester has heard.

## Digital team: score only what stays

An Exploring ask gets four bands, each in one line. The full calibration is
in `50-govern/governance.md`; these are the short versions.

- **Value**: *Tweak* saves one person minutes a week; *Optimiser* removes a
  recurring step for a team or a paper form; *Game change* changes how a
  service operates or removes a known safety or compliance gap.
- **Ease**: *Easy* is buildable from an available pattern in days;
  *Moderate* is a build inside a quarter with one integration or a new
  pattern; *Hard* needs a licence, a new integration, a clinical or
  security review, or longer than a quarter.
- **Evidence**: *Assumed* means the champion heard it once; *Observed* means
  someone watched the workaround; *Measured* means there is a number.
- **Horizon**: *Now* items are ranked against each other; *Next wave* waits
  on readiness; *Later* is a dated deferral; *Strategic* is decided by the
  sponsor and never competes on score.

*Priority Score* is Value times Ease, 1 to 9, and *Priority Band* reads
Later, Consider or Prioritise from it. Evidence sits beside the score and
never multiplies it. An Assumed Game change is a prompt to go and look, not
a prompt to build.

Set **Review Tier** from Data Sensitivity: patient or clinical workflow data
is *Clinical or data review*; sensitive staff or third-party data is
*Security review*; otherwise *Standard*. An ask marked patient or clinical
workflow data, or tiered *Clinical or data review*, shows **Clinical
Reviewer** and **Clinical Review Date**, and the form will not accept it
until the review date is filled. Re-tiering it does not get past that: the
gate reads Data Sensitivity too. Name the reviewer as well; the form cannot
check a person column, so that one is on you.

## Digital team: decide, link to a pattern, check adoption

Setting Status to **Awaiting decision** needs all four bands filled, and so
does every status after it; the form refuses an unscored acceptance. Name
the **Sponsor**, the manager or executive who owns the outcome.

**Accepting** means setting a **Decision Date**, writing the **Decision
Rationale**, and choosing a **Pattern**. If no pattern fits, create one in
`DI_Pattern` first and link it. An accepted ask with no pattern has nothing
to be delivered through, and the *Delivery and adoption* view will show it
under an empty group.

The ask stays **Accepted** while the pattern is built or piloted; the
pattern's own Status shows the progress, so it is recorded once. When the
pattern becomes Available, set **Adoption Check Due** about a month out. It
is highlighted in **Delivery and adoption** once the date has passed.

On that date ask the team whether they use it. Record **Adopted** with an
**Adopted Date** and an **Adoption Note** in one line with a number where
there is one ("phone requests fell from about 40 a week to under 5"), or
**Not adopted** with the reason in Decision Rationale. Both are honest
outcomes; only the second is a lesson.

## Digital team: patterns

`DI_Pattern` holds one row per reusable solution: what it does, which
workloads it uses, whether those are rolled out and licensed today, who
builds it and how hard it is. Status runs Proposed, Building, Piloting,
Available, Retired.

- **Available** needs an **Available Date** and should carry a **Guide or
  exemplar link**; the form checks the date and governance checks the link.
- **Retired** needs a **Retired Date** and a **Retired Reason** saying what
  replaced it.
- *Next Review Due* is calculated twelve months after Available Date. It is
  the reminder to confirm the pattern is still used and still correct.

The count of asks grouped under a pattern in **Delivery and adoption**, and
the Adopted rows that link to it in **Closed and routed**, are the demand
and benefits evidence for that pattern. Ten wards asking for the same flow
is one pattern with ten adoption records, not ten builds.

## Everyone: the log is public

Every ask, including a Routed, Duplicate or Not now one, is readable by
every site member. That is deliberate: a visible backlog is what keeps
demand coming through the front door instead of around it, and a team can
see that its ask was heard before it asks again.

A Not now is not a no. Its Reopen trigger says what would change the
answer, and the digital team re-reads Not now rows at the champions
meeting.
