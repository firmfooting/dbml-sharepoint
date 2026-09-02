# Declarations register: governance

## Ownership

| Role | Held by | Accountable for |
| --- | --- | --- |
| Integrity owner | *(e.g. head of governance / people & culture)* | Thresholds, assessment standards, attestation, this document |
| DR Compliance Coordinators | The maintaining group | Assessment workflow, review cadence, register hygiene |
| Every staff member | n/a | Declaring early and honestly |
| Managers | n/a | Participating in assessments for their people |

## Visibility posture (record the decision)

- [ ] **Open register** (deployed default): all site members read all
      declarations: transparency as the control.
- [ ] **Confidential register**: site membership restricted to the
      compliance function; staff declare via coordinators.

Chosen: ______________  Date: ______  Authority: ______________

## Gift thresholds (edit to your code; keep visible to staff)

**If you change this table, change the data bar too.** `EstimatedValue`
renders as a bar scaled to `max: 200` in `20-configure/mapping.yaml`,
keyed to the ladder below so that anything at or over the "integrity owner
decides" line reads as nearly full at a glance. A bar scaled to somebody
else's ladder means nothing.

| Estimated value | Rule |
| --- | --- |
| Token (under $50) | Declare; may retain unless from a current tenderer |
| $50 - $150 | Declare; manager decides retain/surrender |
| Over $150 | Declare; integrity owner decides; default surrender |
| Any value from a current tenderer/regulated party | Declare; default decline |

## Interest assessment standard

Within 10 business days of a declaration, the coordinator + the declarer's
manager assess: could the interest, seen from outside, influence (or appear
to influence) a duty? Outcomes:

- **Assessed - no action**: no realistic intersection; note why.
- **Assessed - managed**: a written `ManagementPlan` (recusal from named
  decisions, reallocation, information barriers) with an annual
  `ReviewDate`.

The declarer never assesses their own declaration; managers never assess
their own reports' declarations alone.

## Cadences

- **10 days**: assessment SLA for new declarations of either kind. The
  *Awaiting assessment* view is the queue that clock runs against,
  oldest first, so the top row is the one closest to breaching it.
- **Monthly**: coordinators clear *Pending decisions* and chase *Reviews
  due*. Both deploy with the lists. *Reviews due* is a **rolling** thirty
  days, not "this month" (CAML has no calendar-period predicate).
- **Annually**: whole-staff attestation drive. Each person opens *My
  interests*, which shows their own rows and nobody else's. The integrity
  owner reports to the executive/audit committee from *Annual disclosure*
  (a **rolling** twelve months, highest value first) and *By offeror*,
  which is where the repeat-offeror pattern actually reads.

## Data-quality rules

1. Declarations are never edited or deleted. Evolution is a new
   declaration; cessation is a status with a date.
2. Every "Assessed - managed" has a plan and a future ReviewDate.
3. Declined gifts are as much a record as accepted ones.

## What the lists enforce, and what this document does

The strongest control here is not a save rule at all. It is the **form**.
Staff hold a submit-only permission level, so the New form is the only form
most people ever see, and the assessment fields are not on it. The declarer
cannot set `Status`, write a `ManagementPlan` or record a `Decision`,
because those fields do not exist on the form they use. The rule "the
declarer never assesses their own declaration" stops being culture and
becomes structure.

**Enforced at save (SharePoint rejects the row):**

| Rule | List | Where it lives |
| --- | --- | --- |
| Rule 2, the date half: *Assessed - managed* needs a `ReviewDate` | Interest | list validation |
| Rule 1, the date half: *Ceased* needs a `CeasedDate` | Interest | list validation |
| `DeclaredDate` and `CeasedDate` cannot be in the future | Interest | list validation, hoisted from the column rule |
| `OfferedDate` cannot be in the future | GiftBenefit | list validation, hoisted from the column rule |
| `EstimatedValue` cannot be negative | GiftBenefit | column validation |

The two Interest rules share one message, because a SharePoint list has
exactly one `ValidationFormula` and cannot say which branch failed. The
column rules keep messages of their own.

**Still a governance check (nothing stops a wrong entry):**

- **A decided gift needs a `DecisionBy`.** This is the one cross-column
  rule `DR_GiftBenefit` wants and it cannot be written at all: SharePoint
  validation formulas cannot reference a person column, so the build
  refuses it rather than emitting something the platform would reject at
  save. *Annual disclosure* shows **Decided by**, which puts a blank one in
  front of the executive in the report that matters most.
- **Rule 2's management plan.** `ManagementPlan` is rich text, which a
  validation formula cannot reference either. The date half is enforced;
  the plan half is why *Reviews due* carries the column.
- **Rule 1's never-edited, never-deleted.** That is a permission control,
  not a validation one: the **DR Declare Only** level grants
  `AddListItems` and `ViewListItems` and nothing else, so an ordinary
  member physically cannot edit or delete a declaration. Coordinators can,
  and every change is versioned.
- **Rule 3, and declaring at all.** No register can require a declaration
  nobody makes, or a declined offer nobody mentions. The annual attestation
  is the control, and *My interests* is what makes it a two-minute read.

**What the colours do.** *Pending decision* is the only amber state on the
gifts register and the only row anyone has to act on. *Assessed - managed*
is amber on the interests register for the same reason: it is the only
state on that list carrying an ongoing obligation, so it must not share a
colour with *Assessed - no action*. `ReviewDate` turns
red once past, and stops once the interest is *Ceased*.

## Lifecycle

Retention follows your integrity framework (typically long). Export before
decommission; never run `rollback.js.txt` against real declarations.
