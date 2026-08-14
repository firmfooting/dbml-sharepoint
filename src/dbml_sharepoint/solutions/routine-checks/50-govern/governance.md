# Routine checks — governance

## Ownership

| Role | Held by | Accountable for |
| --- | --- | --- |
| Checks owner | *(e.g. quality/facilities/NUM per area)* | The catalogue, missed-check monitoring, this document |
| Checkpoint owner (per row) | `CheckPoint.Owner` | That checkpoint's completeness and follow-up |
| Everyone on the rounds | — | Timely, truthful entries |

## Out-of-range escalation by check type (edit; mirror into Instructions)

| Check type | Immediate action | Escalate to |
| --- | --- | --- |
| Temperature - cold chain | Protect stock per your cold-chain policy; do not use until cleared | Pharmacy/immunisation lead same shift — breach protocol applies |
| Safety equipment | Restock/replace before walking away | Area manager if unable |
| Cleaning / environment | Rectify or log a service request | Facilities per your thresholds |
| Security round | Per your security procedure | Duty manager |

## What is enforced at save, and what stays a governance check

| Enforced at save | Rule |
| --- | --- |
| `Checked At` | Cannot be in the future |
| `CheckEntry` list | An out-of-range result must carry Action taken |
| `CheckPoint` list | An **active** checkpoint must have an Acceptable Range |

Those are data-quality rules 1 and 2 below, in the parts a formula can
reach. Two things about the boundaries, both deliberate:

- **"Unable to check" is not covered by the action rule.** An honest gap
  is a legitimate answer, and demanding a remedy for it is precisely how
  you teach somebody to guess a reading instead. The form still offers the
  action box there, for a word of why.
- **`Instructions` cannot be required.** It is a rich-text column and
  SharePoint validation formulas cannot reference rich text at all. So
  "every active checkpoint has instructions" stays a review item, checked
  when the catalogue is loaded and again whenever a checkpoint's
  escalation changes.

Everything else remains a governance check, and the biggest of them is the
one the platform will never do:

**SharePoint cannot tell you a check did not happen.** A missed check
leaves no row, and no row triggers nothing. Missed-check monitoring below
is people looking, on a cadence — the register makes looking trivial, it
does not make it automatic. Anyone who reads "the system will flag it" into
this template has misread it.

## Missed-check monitoring (the discipline the paper never had)

- **Daily** (checkpoint owners or the checks owner): the **Today** view,
  which is what the entry list opens on — every active checkpoint of
  daily-or-better frequency has its entries. Gaps are followed up **that
  day** while the cause is fresh.
- **Weekly** (checks owner): the **Out of range** view — every entry has
  an Action taken (the list now enforces that, so the review is about
  whether the action was *right*), and then the **Escalated** view —
  every one of those reached its escalation point and somebody closed it.
- **Monthly**: completeness rate per checkpoint (entries ÷ expected), read
  from **By checkpoint** — chronic gaps are a rostering/design
  conversation, and a checkpoint nobody can sustain gets redesigned, not
  ignored.

## The retrospective-entry rule (write it, enforce it)

Entries are made at the time of the check. Reconstructed entries are
prohibited; a missed check is recorded by its absence and managed as a
gap. Timestamps are attributed and versioned — this rule is checkable,
and being checkable is what makes the register audit-grade.

The save rule refuses a *future* Checked At, and its message points here.
It cannot refuse a *back-dated* one: a check genuinely performed at 06:00
and entered at 09:00 is legitimate and common, and a rule tight enough to
catch the fiction would refuse the honest case several times a day. Item
version history carries the created-versus-recorded gap, which is where an
auditor looks.

## Data-quality rules

1. Every active checkpoint: range, frequency, instructions, owner. **Range
   is enforced at save; frequency and owner are required columns;
   instructions are a review item.**
2. Out-of-range entries always carry Action taken. **Enforced at save.**
3. Retired checkpoints go Inactive; their history stays. The **Retired
   checkpoints** view is where they live, and they leave the catalogue
   automatically.

## Lifecycle

Check histories are compliance evidence (cold chain especially) — retain
per your schedule. Export before decommission; never run `rollback.js.txt`
against real rows.
