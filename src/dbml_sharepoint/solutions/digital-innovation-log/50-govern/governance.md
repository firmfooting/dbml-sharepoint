# Digital innovation log: governance

## Governing principle

The log must answer faster than it asks. Every ask is acknowledged within
seven days, decided or given a dated next step within thirty, and every
closure states a reason the requester can read. A log that collects asks
and does not answer them is worse than the notebook it replaced, because the
notebook never promised anything.

## Healthcare boundary

Nothing patient-identifiable enters either list: no patient names, no
clinical record content, no patient-level detail in a Problem Statement.
Describe the process and reference the clinical system where one applies.

**Data Sensitivity** tiers the review that follows and holds no data. An
ask marked *Touches patient or clinical workflow data* takes the *Clinical
or data review* tier, and a registered clinician signs its **Clinical Review
Date** before the ask can be accepted. That is the local expression of NSQHS
Clinical Governance Standard actions 1.10, 1.16 and 1.24, and, where the
service follows it, of DCB0160, under which the organisation deploying
health IT owns the clinical risk and a clinician signs it off. An ask marked
*Touches sensitive staff or third-party data* takes the *Security review*
tier.

An incident, a complaint, a privacy or cyber matter goes to its mandated
system first. The triage route *Incident, complaint, privacy or cyber -
mandated system* records only the hand-off and the receiving reference. See
[`sectors/healthcare.md`](../../sectors/healthcare.md).

## Ownership

| Role | Held by | Accountable for |
| --- | --- | --- |
| Log owner | One named member of the digital team | The response promise, the champions meeting, this document |
| Champion | `DI Champions` members | Capturing asks as heard, telling the requester it is logged |
| Owner | The digital team member named on each Explore here ask | Triage, scoring, the decision and the adoption check for that ask |
| Sponsor | The manager or executive named at acceptance | The outcome, and the Strategic horizon decisions |
| Build Owner | The person named on each pattern | Building it, its guide, its annual review |
| Clinical Reviewer | A registered clinician | Signing a Clinical or data review ask before acceptance |

Every Explore here ask has an Owner, every accepted ask has a Sponsor and
every pattern has a Build Owner. If it is everyone's responsibility it is
nobody's.

## Band definitions

These are the calibration that makes scores comparable across champions and
months. Re-read them aloud at the champions meeting whenever the
distribution drifts.

**Value.** *Tweak*: saves one person minutes a week. *Optimiser*: removes a
recurring step for a team, or a paper form. *Game change*: changes how a
service operates, or removes a known safety or compliance gap. Expect very
few in the top band. If a monthly triage puts more than a fifth of asks
there, the band has drifted and the definitions are re-read aloud.

**Ease.** *Easy*: buildable from an available pattern in days, no new data
connection, one training session. *Moderate*: a build inside a quarter with
one integration or a new pattern. *Hard*: a licence, a new integration, a
clinical or security review, or a build longer than a quarter.

**Evidence.** *Assumed*: the champion heard it once. *Observed*: someone
watched the workaround. *Measured*: there is a number. An Assumed Game change
is a prompt to go and look, not a prompt to build.

**Horizon** is the capacity gate. *Now* items are ranked against each other
and the digital team works the top of that list. *Next wave* items wait on a
Readiness change and are not ranked against Now. *Later* is a dated
deferral. *Strategic* items are decided by the sponsor and never compete on
score.

**Review tier** follows Data Sensitivity. Patient or clinical workflow data
means a clinician signs Clinical Review Date before acceptance. Sensitive
staff data means a security or privacy check. Standard asks get neither.

**Distribution rule.** If more than a fifth of a month's asks land in Game
change, the definitions are re-read aloud at the champions meeting before any
of that month's scores are acted on.

## Response promise

Two targets, stated as local operating targets rather than service promises
encoded in SharePoint:

- **Seven days** from Captured Date to Acknowledged Date. *Acknowledge by*
  is calculated seven days after capture and is red in **Needs response**
  once missed. It stops being red when the ask leaves Captured, so the
  requester is told before the status changes.
- **Thirty days** from Captured Date to a Decision Date or a Receiving
  reference. An Explore here ask that cannot be decided in thirty days gets
  a Horizon of *Later* with a date in the Decision Rationale, and the
  requester is told that too.

A **Not now** must contain a Decision Date, a Decision Rationale the
requester can read, and a Reopen trigger that names the specific change that
would reopen it: a licence arriving, a rollout wave, a system roadmap
dropping the feature. "Not aligned with strategy" tells the requester nothing
and the form refuses a trigger that short.

## The champions meeting

Monthly, one hour, run by the log owner. The agenda has three parts, which
is the shape Microsoft recommends for a champions programme:

1. **What shipped.** Patterns that became Available since last month, read
   from **Catalogue**, and the Adopted rows in **Closed and routed** with
   their Adoption Notes. This is the part champions carry back to their
   teams.
2. **The asks, area by area.** Open **By area** and expand each Service
   Area in turn. Decisions made since last month are read out, Not now rows
   have their Reopen trigger confirmed, and anything still Captured past its
   *Acknowledge by* is assigned on the spot.
3. **What is coming.** New features in the next rollout wave, which *Next
   wave* asks they unblock, and what the champions should listen for next
   month.

Not now rows are re-read here, not re-litigated. A trigger that has fired
reopens the ask as Exploring; one that has not stays where it is.

## Measuring the log itself

Four numbers, each read from a view and reported at the champions meeting
and to the rollout board:

| Metric | Where it comes from | Target |
| --- | --- | --- |
| Time to first response | Median *Days To Acknowledge* over asks captured in the month; the column is in the **System** section of each ask, and a personal view can list it | Median under 7 |
| Share of asks with a written decision | Rows past Captured with a Decision Date or a Receiving reference, over all rows captured 30 or more days ago | Over 90 percent within 30 days |
| Implementation rate | Adopted rows over all rows that are not Duplicate | 10 to 20 percent is normal; higher usually means the scope was narrow |
| Repeat participation | Champions and teams that have raised more than one ask, from Created By and Team or unit | Rising month on month |

The first two are point-in-time reads of today's values. `column-history`,
deployed once on a site the service keeps, is what turns them into a trend:
it records each Status change as a row, so "how long did asks sit in
Captured last quarter" becomes a question the data can answer.

## Data quality checks a formula cannot make

A SharePoint validation formula reads single-line text, choice, number and
date columns, and compares a column with a literal. Lookups, people,
multi-line text and column-to-column comparisons are outside it, so the
following are human checks. Each names the view it is checked in and how
often.

| Check | View | Cadence |
| --- | --- | --- |
| An Accepted or In delivery ask names a Pattern | **Delivery and adoption**: a row under the empty group has no pattern | Weekly, by the Owner |
| A Duplicate names its earlier ask in Merged into | **Closed and routed**: filter Status to Duplicate and open each row | Weekly, at triage |
| A Clinical or data review ask names a Clinical Reviewer | **Exploring**: every row whose Review Tier is *Clinical or data review* | Before acceptance, by the Owner; monthly, by the log owner |
| Acknowledged Date is on or after Captured Date | **By area**: open each row acknowledged since the last meeting and compare the two dates | Monthly, at the champions meeting |
| Available Date is on or after Proposed Date | **Catalogue**: compare the two dates on each pattern made Available since the last meeting | Monthly, by the Build Owner |
| Not now and Not adopted rows have a Decision Rationale | **Closed and routed**: filter Status to Not now, then Not adopted, and open each row | Monthly, at the champions meeting |
| An Available pattern has a Guide or exemplar link | **Catalogue**: the link column is empty | Monthly, by the Build Owner; before any team is pointed at it |

SharePoint does enforce, and the deploy checklist verifies: leaving
Captured needs a Triage Outcome; Awaiting decision needs Value, Ease,
Evidence and Horizon; Accepted and later need a Decision Date; a Clinical
or data review ask needs its Clinical Review Date before acceptance; Not
now needs a Reopen trigger longer than fifteen characters; Routed needs a
Receiving reference; Adopted needs an Adopted Date and an Adoption Note
longer than ten characters; an Available pattern needs an Available Date;
a Retired one needs a Retired Date and Reason; and no dated column accepts
a future date.

## Records and decommissioning

When the rollout ends the log does one of two things. Either it becomes the
standing intake for the digital team, with the champions meeting continuing
at whatever cadence the service sustains, or it is closed. Closing means:
every Captured and Exploring ask is decided or routed, Not now rows keep
their Reopen trigger so a later programme can read what was declined and
why, and `DI_Pattern` stays as the catalogue of what the service built.

Apply the health service records schedule to the asks and decisions. Export
before any decommission and never run `rollback.js.txt` against real rows;
it is for empty and demonstration deployments only.
