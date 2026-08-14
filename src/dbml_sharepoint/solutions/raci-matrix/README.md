# RACI matrix

Who does the work, who answers for it, who must be asked and who must be
told — one row per activity, with the accountability held by exactly one
named person.

The matrix is three lists. **Activity** holds one row per thing that gets
done, approved or decided, carrying a single Responsible and a single
Accountable. **Involvement** holds one row per Consulted or Informed party,
so a consultation list can be as long as it needs to be and every entry has
to say what input it is there for. **Party** is the shared vocabulary of
individuals, roles, governance forums and external bodies that the other two
select from.

Three of the five ways a RACI usually fails are refused by the schema rather
than discouraged by a document: a row cannot carry two Accountables, a team
cannot be made Responsible, and a party cannot be Consulted anonymously.

**The value case.** Most RACI matrices are built in a workshop, drawn as a
wide grid in a spreadsheet, laminated, and dead within six months — because
a grid is a document and an organisation is not. This one is a live
register: it is read-only to everyone and maintained centrally, every row
carries a re-confirmation date driven by how critical the activity is,
and a row anybody believes is wrong can be flagged in one edit and shows up
gold in the default view until somebody deals with it. The question it
answers — *who is accountable for this?* — is one every organisation is
asked in an audit, an incident review and an accreditation, and one most
answer from memory.

**Why three lists and not one wide grid.** Consulted and Informed are
inherently many-valued, and this tool resolves no multi-value person or
lookup column, so a one-row-per-activity RACI could only be built here as
free text. The child list that follows from that constraint is also what
makes the most-cited RACI failure impossible: `Accountable` is a
single-valued person column, so no row can carry two of them, and every
consulted party is a row whose mandatory title has to state the input it
gives.

**The three lists at a glance:**

| List | Columns |
| --- | --- |
| `RACI_Activity` | `Title`, `Domain`, `ActivityKind`, `Criticality`, `Detail`, `Responsible`, `Accountable`, `AccountableForum`, `EscalationRoute`, `ReviewStatus`, `LastConfirmed`, `ConfirmedBy`, `ConfirmationDue` *(calculated)* |
| `RACI_Party` | `Title`, `PartyKind`, `Contact`, `Status`, `Notes` |
| `RACI_Involvement` | `Title`, `Activity`, `Party`, `Involvement`, `Channel`, `Notes` |

`ConfirmationDue` is the only calculated column and is read-only. It is
`LastConfirmed` plus the interval `Criticality` sets — **Statutory 6 months,
High 12, Routine 24** — and it goes blank on a retired activity, because
nobody needs to re-confirm work that has stopped. Past due it turns red with
a warning icon, and that escalation is suppressed on a retired row.

**Eleven declared views**, deployed with the paste — nothing to build by
hand. On Activity: *Current* (the default), *My accountabilities*,
*Confirmation due*, *Decisions and approvals* (grouped by the forum that
owns them) and *Retired*. On Involvement: *By activity* (the default — this
is the matrix as it is normally drawn), *By party*, and *Consultation load*,
which is grouped by party rather than by activity because the failure it
exists to reveal — one party made Consulted on everything — is invisible in
any activity-first view. On Party: *Active parties* (the default), *By kind*
and *Retired parties*.

**One row-level signal in the whole template.** A *Needs review* activity
washes gold in the **Current** view. It is reserved for the one state
nothing else shouts about: a human has said this row is wrong, which is
worse than a date having passed.

**Nine supported SharePoint indexes** are declared in `schema.dbml`:
`ReviewStatus`, `Criticality`, `Accountable` and `Domain` on Activity;
`PartyKind` and `Status` on Party; `Activity`, `Party` and `Involvement` on
Involvement. SharePoint cannot index the calculated `ConfirmationDue`, so
the two views driven by that date are not guaranteed to scale past the
list-view threshold without redesigning it as a persisted field.

**Three save rules on Activity.** A Decision must carry an escalation
route, and so must anything Statutory — both are cross-column rules and so
share the list's single validation message. The third reads only its own
column and keeps a message of its own: `LastConfirmed` is required and
refuses a date in the future. The escalation-route field appears on the
form in exactly the two cases the first two rules cover, so the register
never refuses a save while naming a field the author cannot see.

**Work the folders in order:**

| Step | Folder | You |
| --- | --- | --- |
| 1 | `10-design/` | Fit `Domain` to how your organisation divides work |
| 2 | `20-configure/` | Prefix; **the confirmation cadence lives here** — changing it recalculates every row |
| 3 | `30-deploy/` | Administrator: build, paste, verify, **then seed `Party` first** |
| 4 | `40-adopt/` | The staff guide: the four letters, the five failure modes, and what this register is not for |
| 5 | `50-govern/` | Review cadence, the departed-person workflow, the two checks SharePoint cannot enforce |

**Read the staff guide before rolling this out**, and not only because
staff need it. It is where the method itself lives — what Responsible and
Accountable mean in a Task versus an Approval versus a Decision, why RACI
governs execution and has no decider (so a team using one to *make* a
decision deadlocks, and wants DACI or RAPID instead), and the honest
objection that a rigidly-applied RACI is an excellent instrument for a
blame culture. A register deployed without that briefing gets the failure
modes anyway.

**Customisation points:** the `Domain` enum; the three intervals in the
`ConfirmationDue` formula in `mapping.yaml` (read the change-control section
of `50-govern/governance.md` first — changing one recalculates every
existing row, and shortening one makes rows overdue the moment the paste
finishes); the `involvement_channel` list, which should name the meetings
and reports your organisation actually has; and how wide `RACI Matrix
Maintainers` should be, which the governance file sets out as a real choice
with a cost either way.

**Demo data.** Build with `--seed` and the bundle gains a `demo-data.js.txt`
that pastes eighteen rows titled with `[DEMO]` followed by a space — six
parties covering all four
kinds plus a disbanded forum, six activities including an overdue Statutory
one flagged *Needs review* and a retired one, and six involvements, three of
them consulting the same external auditor so the *Consultation load* view
has something to show. Every declared view returns rows and every formatted
column renders in its colours. See `30-deploy/deploy.md`.
