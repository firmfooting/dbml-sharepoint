# RACI matrix — governance

## Ownership

| Role | Held by | Accountable for |
|---|---|---|
| Register owner | *(e.g. head of governance / company secretary / COO)* | That the register describes the organisation as it is today; the quarterly review; this document |
| Accountable (per row) | The `Accountable` column | That the activity happens, and that the row describing it stays true |
| Responsible (per row) | The `Responsible` column | Doing the work, and saying when the row no longer matches reality |
| RACI Matrix Maintainers | The maintaining group | Data entry, the party vocabulary, working the confirmation queue |

**Naming somebody in `Responsible`, `Accountable`, `ConfirmedBy` or a
party's `Contact` grants them nothing.** Those are person columns, not
permissions: `list_permissions` gives Contribute to **RACI Matrix
Maintainers** and Read to the site's associated members and owners under
`reconcile: exact`, and SharePoint has no item-level grant derived from a
person column.

So a person accountable for forty activities who is not in RACI Matrix
Maintainers cannot re-confirm one of them, cannot correct a row they know
is wrong, and cannot flag it *Needs review* — the acts this table makes
them accountable for.

**That is a deliberate posture, not an oversight.** A register whose
subjects can rewrite their own accountability is not a register: the
value of the thing is that the rows were written centrally, from the
organisation's point of view, rather than negotiated by the people they
describe. The cost is that every correction goes through a maintainer,
which is real work and needs a real group to absorb it.

Two ways to size that group, and you must pick one before rollout:

- **Small and central** (the default): three to six people in governance,
  quality or executive support. Corrections arrive by conversation or
  email. Keeps the register consistent; needs someone to own the inbox.
- **Wider**, with the accountable population inside RACI Matrix
  Maintainers. Faster corrections, at the cost that anyone can adjust
  their own row — so pair it with the change-visibility habit below.

Versioning is on with 200 major versions retained, so either way every
edit leaves a version-history entry naming who made it. Where the
group is wide, the register owner spot-checking recent version history at
each quarterly review is what keeps the first option's guarantee alive in
the second option's shape.

## Review cadence

**Quarterly, as a standing rhythm, plus on any material organisational
change.** Both halves matter, and the second is the one that gets skipped.

The per-row `ConfirmationDue` cadence — Statutory 6 months, High 12,
Routine 24 — is the **floor, not the ceiling**. It is the longest a row
may go unexamined before the register admits it does not know whether the
row is true. It is not a schedule for reviewing the register, and a
register reviewed only when rows fall due drifts for up to two years in
its Routine half.

**Material change means, at least:** a restructure, an executive or
senior appointment or departure, a committee created, merged or
disbanded, a new statutory or funding obligation, a service moved between
teams, an outsourcing or in-sourcing, and any incident whose review found
that nobody was clear who owned something.

### What a quarterly review consists of

1. **Work the *Confirmation due* view.** Everything falling due in the
   next thirty days or already past. Each row gets re-read, corrected if
   needed, and confirmed — `LastConfirmed` to today and `ConfirmedBy` to
   whoever actually checked. An edit is not a confirmation.
2. **Work every *Needs review* row.** These are the rows a human has said
   are wrong. They are the highest-value rows in the register and they
   should not survive two consecutive reviews.
3. **Read the *Consultation load* view.** See below — this is the review
   step most likely to be dropped and the one that catches a failure
   nothing else can see.
4. **Read *Decisions and approvals*, grouped by forum.** Every non-Task
   row should have an escalation route that names somebody reachable, and
   the forum it is grouped under should still exist.
5. **Check *Active parties* against the org chart.** Anybody who has left,
   and any forum that has been disbanded, gets the departed-party
   workflow below.
6. **Look for the activities that are not there.** The register's most
   dangerous gap is the work nobody wrote down, and no view can show you
   an absent row. Walk the `Domain` list and ask, per domain, what
   statutory or high-consequence work is missing.

## The consultation-load review

**Read the *Consultation load* view at every quarterly review, and
challenge any party consulted on more than a handful of activities.**

That view exists for one purpose: it is grouped by party rather than by
activity, because the failure it hunts — one party made Consulted on
everything — is invisible in any activity-first view. Reading the
register activity by activity, three consultations per row looks
reasonable everywhere while one person is quietly Consulted on sixty
rows.

A long list under one party is not proof of anything, so challenge rather
than delete. Ask, per involvement: *what input does this party give, and
would the activity actually stop without it?* The involvement Title is
supposed to answer the first half already. Where it does not, or where
the honest answer to the second half is no, the involvement is
**Informed** and should be changed to it.

What you are protecting against is the C column drifting from a
functional input list into a political protection list — a record of
everyone who would be annoyed to be left out. That version of the column
slows every activity it touches and tells you nothing, and it arrives
politely, one reasonable addition at a time.

Set your own threshold and write it here: challenge any party over
______ consulted involvements. A number written down is challenged; a
vague sense of "a lot" is not.

## The departed-person workflow

Somebody leaves, a role is abolished, a committee is disbanded. Work it
in this order.

1. **Set the `Party` row to Inactive** and update its `Contact` to
   whoever now holds the role, chairs the successor forum, or is the
   point of contact in the interim. `Status` drives the *Active parties*
   and *Retired parties* views, so this is what takes them out of every
   picker's working view.
2. **Never delete a `Party` row.** Every activity's `AccountableForum`
   and every involvement's `Party` is a lookup at it, and deleting the
   row orphans all of them — the child rows survive pointing at nothing,
   which reads as a blank cell rather than as an error. Inactive keeps
   the history readable: the rows that named the Regional Partnership
   Forum still say so, and the party row still explains what it was.
3. **Work the activities that named the person.** Both `Responsible` and
   `Accountable` are columns on the **Current** view, so the rows naming
   them can be found by filtering or sorting that view — which is the
   argument for person columns over free text, quite apart from the
   argument about teams. Reassign each row to whoever now holds the work.
   This is the step that takes real time, and it is the step
   that matters: an activity whose Accountable left three months ago is a
   row that reads as owned and is not.
4. **Work the involvements.** *By party* is grouped for exactly this:
   every involvement naming that party, in one place. Repoint them at the
   successor or retire them.
5. **Confirm each row you touched** — `LastConfirmed` and `ConfirmedBy` —
   so the cadence restarts from a row somebody actually verified.

A departure is also the moment to check the reverse direction: work the
person was doing that the register never captured leaves with them, and
nothing in the register can tell you about it. Ask them.

## Two checks SharePoint cannot enforce

Both of these are human work. Neither is a gap somebody forgot to close,
and stating them here rather than implying the platform handles them is
the point of this section.

**1. A non-Forum party should name a `Contact`.**

An Individual, a Role or an External party with no contact is a name
nobody can act on: the register says the Practice Manager is Consulted on
something and nobody can tell you who to email. A Forum is the reasonable
exception, and even there the chair or secretariat is usually worth
recording.

This **cannot** be enforced at save. `Contact` is a person column, and
SharePoint validation formulas refuse person operands entirely
(`analysis/conditions.py:332` is where the build refuses to write such a
rule rather than emitting one that silently never fires). There is no
conditional form of it either — "required unless PartyKind is Forum" is
the same refusal for the same reason.

The control is the **Active parties** view, which carries `Contact` as a
column precisely so a blank is visible while reading the vocabulary. A
maintainer scanning that view at each quarterly review is the whole
mechanism.

**2. One activity, one Accountable.**

Enforced *within a row*: `Accountable` is a single-valued person column,
so no row can carry two. That is the structural claim this template
makes and it holds.

What no list can see is **the same work described twice**. "Approve a new
supplier above the executive threshold" and "Sign off new vendor
contracts over the delegation limit" may be one activity with two rows
and two different Accountables — and every failure of two Accountables on
one row is reproduced exactly, with the added feature that neither person
can see the other's row unless they go looking.

Nothing can detect it. It is not a duplicate title, not a duplicate
lookup, not a formula anything can write; recognising it needs somebody
who knows the business reading two rows in different domains and seeing
that they are the same work. Two habits reduce it:

- **`Detail` writes the boundary.** A row that says what it does *not*
  cover is the only thing that makes an overlap visible on the page.
- **Read the register by `Domain` at review**, not by due date. Duplicates
  cluster near each other in subject and nowhere near each other in
  cadence.

## What the register does enforce

| Rule | Where |
|---|---|
| Exactly one Responsible and one Accountable, both individuals | The column types — a person column, single-valued |
| A team cannot hold either | The column types — a group is not a selectable value |
| An involvement names an activity, a party and the input it gives | Required columns |
| A Decision has an Escalation Route | list validation (shared message) |
| Anything Statutory has an Escalation Route | list validation (shared message) |
| `LastConfirmed` is required and never in the future | required field + column validation (own message) |

The two escalation rules share one message because SharePoint gives a
list a single `ValidationFormula`. The `LastConfirmed` rule reads only its
own column, so it lives in `column_validation` and keeps a message that
can be specific.

Note the interaction the deploy guide flags: the escalation rule fires on
anything Statutory, while the field is only *shown* when the kind is not
Task. A Statutory Task is therefore refused while naming a field that is
off the form. It is enterable — set the kind to Approval or Decision,
type the route, set it back — and `30-deploy/deploy.md` sets out the two
ways to resolve it if that edge is too sharp for your register.

Every other rule in this document is a governance check, because the
platform cannot express it. That includes everything in the two sections
above, the consultation-load challenge, and the judgement that an
activity is worth being in the register at all.

## Change control on `ConfirmationDue`

The cadence is one formula in `20-configure/mapping.yaml`, under
`calculated_formulas`. **Editing it recalculates every existing row**:
SharePoint recalculates a calculated column across the whole list the
moment the formula text changes, and a redeploy is exactly that change.

Two consequences worth thinking about before you touch it:

- **Shortening an interval falls due immediately.** Taking Routine from
  24 months to 12 does not schedule a gentler future; it makes every
  Routine row confirmed more than a year ago overdue the moment the paste
  finishes, with the red treatment on all of them. That may be exactly
  what you want — plan the review capacity for it rather than discovering
  it.
- **The formula is keyed to the `criticality` enum by name and by order.**
  It maps *Statutory* and *High* explicitly and treats everything else as
  Routine, so a member added, renamed or reordered in `schema.dbml`
  silently receives the **longest** interval rather than failing. The
  comment above the formula says so at the place somebody editing the
  enum will look. Change the enum and the formula together, or not at
  all.

Export the register to Excel before any cadence change — that snapshot
preserves the due dates as they stood immediately before it.

### A known defect, accepted and tracked

Adding months with `DATE(YEAR(d), MONTH(d)+N, DAY(d))` **overflows at
month end rather than clamping**: a confirmation recorded on 31 August
falls due on 3 March rather than 28 February. It is one to three days on
a cadence of six months or more, against a column whose own guidance is
to re-confirm sooner on any material change, so it is accepted rather
than worked around. It is tracked as issue #5, and `risk-register` carries
the same defect for the same reason. Do not "fix" it locally without
reading that issue — the arithmetic that clamps correctly is
substantially longer and recalculates every row to install.

## Hand-offs to other registers

Templates in this library interconnect by **process hand-off, never by
list lookups**. Every template deploys and stands alone; nothing below
creates a dependency, and no column here points at another register.

**`delegations-register` — authority.** This register records who *does*
the work and who *answers* for it. It does not record who is *permitted*
to approve what: that authority lives in your formally approved
instrument of delegation, which `delegations-register` mirrors clause by
clause. The two must agree, and where they disagree **the instrument
wins** — it is the approved document and this is a description of
practice. So: when an Approval or Decision activity names an Accountable
who does not hold the corresponding delegation, that is a finding about
the RACI row, not about the delegation, and it is fixed here. Check the
non-Task rows against the instrument at each quarterly review; the
*Decisions and approvals* view is the list to check them from.

**`risk-register` — consequence.** Two hand-offs run between these, both
by hand:

- An activity that is Statutory, or whose failure would cause serious
  harm, and that has **no credible Accountable** — vacant, departed, or
  genuinely contested — is a risk in its own right. Raise it in the risk
  register, describing the accountability gap as the cause. Do not leave
  it sitting as a *Needs review* row that everybody has stopped seeing.
- A control in the risk register almost always names an activity
  somebody has to perform. That activity belongs here, with a named
  Responsible and Accountable. A control nobody is accountable for
  performing is a control on paper, which is the most common way a
  treated risk turns out to have been untreated.

Both directions are prose in a review conversation, deliberately. A
lookup between two registers would tie their deployments, their
permissions and their lifecycles together, and neither register would
survive the other being retired.

## Data-quality rules

1. **Activities are verb phrases**, and `Detail` states the boundary —
   what this activity covers and what it does not. A noun with no
   boundary is a topic, and a topic cannot have an Accountable.
2. **Every involvement Title states an input**, not a person and not a
   reason for courtesy. "Pricing tolerance and contract terms", not
   "Because they'll want to know". A party you cannot write that sentence
   for is Informed, or nothing.
3. **The party vocabulary is the vocabulary.** New parties are added
   deliberately, not invented per row. Two rows for the same committee
   under two spellings split every grouped view that exists.
4. **Retire, never delete** — parties by `Status`, activities by
   `ReviewStatus`. The history of who used to be accountable for
   something is frequently the reason somebody opens this register.
5. **Confirming is re-reading**, not re-saving. `ConfirmedBy` records who
   actually checked; it is not the same as who last edited the row.

## This register is not an HR record

It records how work is organised, not how people perform. It carries no
assessment of anybody, and it should never be used as one: a row that
falls due is a row nobody has re-read, not evidence about the person
named in it. Keeping that line clean is what makes people willing to mark
their own rows *Needs review*, which is the behaviour the whole register
depends on.

## Sealed columns and deletion protection

This register uses the fleet-standard hardening declared in
`mapping.yaml`: `seal_columns: true` blocks UI schema edits and deletion
of every deployed column, even for site admins (a display-name rename
still gets through — that is drift, reverted and reported at the next
re-paste), and `prevent_list_deletion: true` removes "Delete this list"
from all three lists for everyone. Both are friction and tamper-evidence,
not enforcement against a determined site collection admin working
through the API — see "Hardening and drift detection" in
[`templates/README.md`](../../README.md). The deploy script unseals for
its own run and re-seals afterwards; nobody else should need to.

## Lifecycle

Export all three lists before decommissioning, and export `Involvement`
with its lookups resolved — an involvement exported without its activity
and party is a sentence about an input with nothing attached to it.

Never run `rollback.js.txt` against a populated register. It is for a
failed first provision on an empty site, and for clearing demo data
seeded with `--seed`.
