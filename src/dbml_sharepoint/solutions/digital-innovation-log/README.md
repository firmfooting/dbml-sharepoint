# Digital innovation log

*Theme: process digitisation & improvement.*

The M365 asks a rollout hears, captured once by a champion, routed before
they are scored, and delivered through a pattern built once. Every ask is
acknowledged within a week and checked for adoption afterwards. Two lists:
`DI_Opportunity` (one row per ask) and `DI_Pattern` (one row per reusable
solution).

**The value case.** During an M365 rollout the same asks come up in every
workshop and floor walk: "can Teams do our roster", "we still print this
form", "who approves leave now". They live in champions' notebooks and the
digital team's inbox, most are never answered, and the same ask is heard from
five wards without anyone noticing it is one ask. This log answers every ask,
builds the solution once, and records whether the team that asked actually
used it. That last column is the rollout's benefits story.

**Route before you score.** Most asks are helpdesk tickets, training gaps or
duplicates. Triage picks one of eight routes, sends the ask where it belongs
with a reply, and only an ask worth an M365 build is scored:

| An ask that is really... | Route | Terminal status |
| --- | --- | --- |
| A helpdesk request or fault | service-requests or your helpdesk | Routed |
| A capability that already exists | Show and train; link the how-to | Routed |
| A process change with no M365 build | improvement-register | Routed |
| A project-sized change | project-pipeline | Routed |
| An incident, complaint, privacy or cyber matter | The mandated system | Routed |
| The same ask another team already raised | Merged into that row | Duplicate |
| Not worth doing now | Declined with what would change the answer | Not now |
| An M365 build worth exploring | Stays here | Exploring onwards |

**Build on the pattern, adopt on the ask.** Delivery status lives on the
pattern, in one place. Adoption lives on each ask, per team. Ten wards asking
for an approvals flow link to one pattern, and each of the ten rows records
whether that ward adopted it.

**Scoring without false precision.** `Priority Score = Value x Ease`, each in
three descriptive bands, giving 1 to 9. Evidence (Assumed, Observed, Measured)
sits beside the score and never multiplies it. Horizon is the capacity gate:
only Now items are ranked against each other, and Strategic items are decided
by their sponsor rather than by score.

| Input | 1 | 2 | 3 |
| --- | --- | --- | --- |
| Value | Tweak | Optimiser | Game change |
| Ease | Hard | Moderate | Easy |

| Score | Band |
| ---: | --- |
| 1 to 2 | Later |
| 3 to 4 | Consider |
| 6 to 9 | Prioritise |

**The response promise.** `Acknowledge by` is calculated seven days after
capture and turns red while the ask is still Captured. A *Not now* must say
what would change the answer. Both are what keeps demand coming through the
front door instead of around it.

**Eight declared views**, deployed with the paste. Opportunity: *Needs
response* (the default, oldest first), *Exploring* (grouped by Horizon,
score descending), *Delivery and adoption* (grouped by Pattern, so the count
under each pattern is the "twelve teams want this" evidence), *By area* (the
champions meeting view) and *Closed and routed*. Pattern: *Catalogue* (the
default), *In build* and *Retired*.

**Save rules.** Leaving Captured needs a triage route. Awaiting decision needs
Value, Ease, Evidence and Horizon. Accepted and later need a decision date,
and a Clinical or data review ask needs its review date first. Not now needs
its reopen trigger, Routed its receiving reference, Adopted its date and what
changed. Lookups, people and multi-line text cannot be read by a SharePoint
validation formula, so "Accepted needs a Pattern" and "a clinical ask names
its reviewer" are governance checks, and `50-govern/governance.md` says so.

**Work the folders in order:**

| Step | Folder | You |
| --- | --- | --- |
| 1 | `10-design/` | Replace Service Area with local language; trim the workload list to what you licence |
| 2 | `20-configure/` | Prefix; champions and digital team groups; the capture-guide link |
| 3 | `30-deploy/` | Administrator: build, paste, verify both lists |
| 4 | `40-adopt/` | The champion's capture guide and the digital team's triage habit |
| 5 | `50-govern/` | Band definitions, the response promise, the champions meeting, the log's own metrics |

**Customisation points:** `service_area` and `m365_workload` in the schema;
the seven-day acknowledgement in `AcknowledgeBy`; the `max:` on the
`DaysToAdopted` bar, which ships at 120 days. Five views filter on `Status`
members by name, so a renamed member empties a view without failing the
build.

**Demo data.** Build with `--seed` and the bundle gains a `demo-data.js.txt`
that pastes five `[DEMO]` patterns and fifteen `[DEMO]` asks: two awaiting a
response (one overdue), one per triage route, a duplicate merged into an
accepted ask, a clinical-review ask, and an adopted ask with a measured note.
See `30-deploy/deploy.md`.
