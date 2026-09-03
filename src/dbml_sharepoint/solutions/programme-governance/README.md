# Programme governance

Programme governance on ten lists, from workstreams and standing
accountabilities to service requests, risks, actions, issues and decisions.
Ten lists: `GOV_Workstream`, `GOV_Stakeholder`,
`GOV_Activity`, `GOV_Involvement`, `GOV_ServiceRequest`,
`GOV_Risk`, `GOV_Action`, `GOV_Issue`,
`GOV_Decision`, `GOV_BusinessProcess`.

**The value case.** A programme run by an organisation that does not
administer its own platform fails in three places at once, and no single
template in this library covers all three. The worked example throughout is an
M365 adoption programme in a health service whose tenant a shared-service
provider holds, which is where the family was built. Delivery drifts, which a
RAID log catches. Accountabilities rot, which a RACI matrix catches. And the
changes that actually unblock the work are made by somebody else's tenant
team, which neither catches. This family is one site holding all three,
because they are read together: an issue is usually a service request that has
sat with the provider for three weeks, and the person who can escalate it is
whoever the accountability register says it is.

**Ten lists, and what each one is for:**

| List | Holds | The question it answers |
| --- | --- | --- |
| `GOV_Workstream` | The programme's five to eight streams of work | What are we actually doing, and in what order |
| `GOV_Stakeholder` | People, roles, forums and external bodies | Who is involved, and how do we reach them |
| `GOV_Activity` | Standing accountabilities, one Responsible and one Accountable | Who is accountable for this when it goes wrong |
| `GOV_Involvement` | Who is consulted or informed on an activity | Who else has a say, and how they get it |
| `GOV_ServiceRequest` | Every change only the provider can make, worked from draft to closure | What have we asked for, who is on it, and where has it stuck |
| `GOV_Risk` | Uncertain events, rated on a 5x5 matrix | What could still stop this programme delivering |
| `GOV_Action` | Work handed to a named person with a date | Who is doing what, and by when |
| `GOV_Issue` | Things that have already gone wrong | What is hurting the programme right now |
| `GOV_Decision` | Decisions and why they were made | Why we did it that way |
| `GOV_BusinessProcess` | Project-adjacent processes worth mapping, and where each map lives | Which process to map next, and who owns it today |

The family's prefix is `GOV_`, so the list titles are `GOV_Workstream`,
`GOV_Stakeholder`, `GOV_Activity` and so on, and the three family groups and
two permission levels carry the same stem: `GOV Programme Leads`,
`GOV Submit Only`. GOV names what the lists are, which is the level the other
families name at (`RR_`, `RACI_`, `RAID_`), rather than the programme they
happen to serve. The family's own name now says the same: it was
`m365-adoption-program`, which named one programme rather than the register
every programme needs. Entity names are unique within the family, and the
prefix is what keeps families apart on a shared site.

**The provider boundary is the design decision that matters.** The health
service does not hold tenant administration; a shared services provider does,
and every change the programme needs from the provider is a row in
`GOV_ServiceRequest`, worked on that row from draft to closure. The health service
records what it is asking for, why, who authorised it internally and when it
is needed. The provider's handler picks the row up, holds it through
`In progress` and `Waiting on requester`, closes it, and records the minutes
spent on it, so the effort the arrangement costs is counted on the same row
as the authorisation. `Waiting on requester` is the hand-back: the handler
needs something from the health service before the work can continue, and
the request stays open and visible until it comes.

**Nothing moves past `Drafted` on the way in.** `Status` is hidden from the
New form and defaults to `Drafted`, and the site's members hold
`GOV Submit Only`, which can add an item and read every list but cannot edit
one. Anybody may record a request, because a bottleneck at the point of entry
is how a record stops being complete; only `GOV Programme Leads` and the
handlers in `GOV Request Handlers` can change one afterwards, and only
governance authorises. Neither half is the control on its own.

**Self-service confirmation, with version history as the audit.** The three
accountability lists are edited through `GOV Accountability Maintainers`, a
deliberately wide group holding `GOV Contribute No Delete`: add and edit,
read version history, but no deleting an item and no pruning its history.
SharePoint cannot express "edit only your own row" against an arbitrary
person column, so the mechanism is a wide group that cannot destroy anything
and a quarterly review that reads the history of every row changed since the
last one. Those three lists keep 200 versions rather than the 100 the other
six keep, for that reason.

**Five permission classes**, every list with inheritance broken and
`reconcile: exact`, so anything granted by hand is removed on the next
deploy:

| Class | Lists | Site members get |
| --- | --- | --- |
| A | `Workstream` | Read |
| B | `Risk`, `Action`, `Issue` | Contribute |
| C | `Decision` | `GOV Contribute No Delete` |
| D | `Activity`, `Stakeholder`, `Involvement` | Read, plus maintainers on `GOV Contribute No Delete` |
| E | `ServiceRequest` | `GOV Submit Only`, plus handlers on `GOV Contribute No Delete` |

`GOV Programme Leads` holds Contribute everywhere, and the two shared
groups (`dbml List Administrators` at Full Control,
`dbml Enterprise Readers` at Read) are on every list, as they are across the
library. All three family groups are created empty and their membership is
never reconciled, so populating them is a go-live step in `30-deploy/`.

**The risk matrix is the risk-register matrix.** Pick **Likelihood** and
**Consequence** and SharePoint calculates **ResidualRiskRating**
(Low/Medium/High/Extreme) and a 1-25 **RiskScore**. There is nowhere to type
a rating that disagrees with the matrix, because the rating is never typed.
`GOV_Activity` carries the RACI matrix's **ConfirmationDue**, which falls
6, 12 or 24 months after the last confirmation depending on criticality.

**Three lookups are nullable on purpose.** `Action.RelatedRisk`,
`Action.RelatedServiceRequest` and `Issue.RelatedRisk` are all
optional, because most actions are ordinary programme work and most issues
arrived out of nowhere. The risk pickers offer only **live** risks, through a
calculated `LiveRiskTitle` that is blank once a risk is Closed, while views
show the real `Title` through a read-only projection. `GOV_Action` also
projects its workstream's `Phase`, so an action filed against a closed
workstream is visible in every action view: a lookup picker cannot be
filtered, so the mistake is shown rather than prevented.

**Forty-three declared views**, deployed with the paste:

| List | Views |
| --- | --- |
| `GOV_Workstream` | *The programme* (the default, in sequence) |
| `GOV_Stakeholder` | *Active stakeholders* (the default), *By kind* (grouped), *Retired stakeholders*, *Changed since last review* |
| `GOV_Activity` | *My accountabilities* (the default), *Confirmation due*, *Never confirmed*, *Needs review*, *By workstream* (grouped), *Workstream leads* (grouped), *Decisions and approvals* (grouped by forum), *Retired*, *Changed since last review* |
| `GOV_Involvement` | *By activity* (the default, grouped), *By stakeholder* (grouped), *Consultation load* (grouped), *Changed since last review* |
| `GOV_ServiceRequest` | *In progress* (the default), *Authorised, not yet picked up*, *My assigned requests*, *Closed* (with the minutes totalled), *Escalated*, *Needed soon or overdue*, *My raised items*, *Changed since last review* |
| `GOV_Risk` | *Open* (the default, worst first), *Review due*, *Closed this quarter* |
| `GOV_Action` | *My actions* (the default), *Overdue*, *Open by person* (grouped), *Done and dropped* |
| `GOV_Issue` | *Open* (the default, grouped by workstream), *Severe and open*, *By owner* (grouped), *Needs triage*, *My raised items*, *Resolved and closed* |
| `GOV_Decision` | *Awaiting decision* (the default), *Decision log*, *Stalled proposals*, *Changed since last review* |

**What the lists cannot enforce.** SharePoint validation formulas refuse
multi-line, person and lookup operands, so five obligations the governance
register carries are human checks rather than save rules: a closed risk
carries a closure note; an authorised request names who authorised it; a
request being worked names its handler; an external stakeholder names a service
desk address; and the provider is never the Accountable on an activity. Each
has a view that surfaces it. The rules that *can* be enforced are, including
a chained rule on `GOV_ServiceRequest` and a three-branch escalation-route rule
on `GOV_Activity`.

**Work the folders in order:**

| Step | Folder | You |
| --- | --- | --- |
| 1 | `10-design/` | Fit the request types, criticality and phase choices to your programme |
| 2 | `20-configure/` | Prefix, permissions and views; **the matrix lives here**, edit with care |
| 3 | `30-deploy/` | Administrator: build, paste, populate the three groups, disable attachments |
| 4 | `40-adopt/` | Programme team guide: the fortnightly and the quarterly, plus step-by-step tasks in `40-adopt/workflows/` |
| 5 | `50-govern/` | The permission model, the quarterly review, and what a probe would have to show |

**Customisation points:** the `adopt_request_type` enum, which is the one
list most likely to be wrong for another provider; the escalation levels in
`adopt_escalation_level`, which should match your own agreement rather than
these; the matrix cells and the confirmation cadences in `mapping.yaml`; and
the nine form straplines under `20-configure/formatting/`, which are what
somebody reads before typing anything. Three of them carry a sentence about
patient-identifiable data. That sentence is guidance and nothing checks it,
so treat it as a prompt rather than a control.

**Demo data.** Build with `--seed` and the bundle gains a `demo-data.js.txt`
that pastes six workstreams, seven stakeholders, nine activities, seven
involvements, seven service requests, six risks, seven actions, seven issues and
seven decisions, all `[DEMO]`-titled, spanning every status and every rating
band so no declared view is empty on a first look. See `30-deploy/deploy.md`.
