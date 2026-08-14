# Compliance obligations — governance

## Ownership

| Role | Held by | Accountable for |
| --- | --- | --- |
| Compliance owner | *(e.g. head of governance/quality)* | The register's coverage, assessment standard, reporting, this document |
| CO Compliance Coordinators | The maintaining group | Loading, assessment facilitation, evidence currency |
| Obligation owner (per row) | `Owner` | The duty being met and evidenced; raising changes early |

## Assessment standard

A status is real only when set **against sighted evidence** with the
owner, and dated (`LastAssessedDate`):

- **Compliant** — evidence current and linked; the practice it evidences
  actually happens (spot-check, don't just file-check).
- **Partially compliant** — met in part or in some areas; the gap is
  named in Notes with a remediation pointer (change-register or
  improvement-register item).
- **Non-compliant** — the duty is not being met; escalation below applies.
- **Not applicable** — with the reasoning recorded; reviewed like any
  other row (applicability changes).

## Non-compliance handling

1. Any row moving to Non-compliant: compliance owner informed same day;
   the responsible executive within 5 business days.
2. Every Non-compliant/Partially compliant row carries a remediation
   pointer with an owner and date — the *gap list* view is a worklist,
   not a wall of shame.
3. Honest reporting is protected explicitly: gaps raised by owners are
   treated as the system working. (Regulatory self-disclosure decisions
   remain with the executive per your obligations — the register informs
   them, it doesn't make them.)

## Review cycles

| Status / stakes | Reassess at least |
| --- | --- |
| Non-compliant / Partially compliant | Monthly until resolved |
| Compliant, high-stakes instruments (safety, funding conditions) | Annually |
| Compliant, other | Every 2 years |
| Accreditation standards | Aligned to your accreditation cycle, front-loaded before assessment visits |

## Reporting

- **Quarterly** to the executive/audit committee: the gap list with
  remediation status; counts by instrument; anything Not assessed older
  than 6 months.
- **Pre-accreditation**: the *By source* view for the relevant standard IS
  the self-assessment evidence index. It deploys with the list, grouped by
  source type and then by the named instrument inside it, both collapsed —
  expand your standard and the rows underneath are the pack.

## Data-quality rules

1. No status other than Not assessed without LastAssessedDate + evidence.
2. Every row has a human Owner; leavers reassigned within a month.
3. Instrument changes trigger a recorded sweep (dated in Notes).

## What the list enforces, and what this document does

Rule 1 is now refused at save. Rules 2 and 3 cannot be, and the reasons are
worth knowing rather than discovering.

**Enforced at save — SharePoint rejects the row:**

| Rule | Where it lives | Message shown |
| --- | --- | --- |
| A status other than *Not assessed* needs a `LastAssessedDate` | list validation | Shared, names both list rules |
| *Compliant* / *Partially compliant* / *Non-compliant* needs `EvidenceNotes` | list validation | Shared, names both list rules |
| `LastAssessedDate` cannot be in the future | column validation | Its own message, on the column |

The two list rules share one message because a SharePoint list has exactly
one `ValidationFormula` — it cannot say which branch failed, so the message
names both checks rather than guessing. The future-date rule reads only its
own column, so it lives there and keeps a message of its own.

*Not applicable* is exempt from the evidence rule. Its reasoning belongs in
`Notes`, and requiring evidence of a duty that does not apply would be
asking for the wrong artefact.

**Still a governance check — nothing stops a wrong entry:**

- **The remediation pointer on every gap row.** It lives in `Notes`, which
  is rich text, and a SharePoint validation formula cannot reference a
  multi-line column at all. *The gap list* view shows `Notes` beside the
  status precisely so its absence is visible in the monthly review.
- **Rule 2, an Owner that is a real current person.** `Owner` is required
  at the schema level, so it cannot be blank — but person columns cannot
  appear in a validation formula, so "the owner still works here" is
  unreachable. The annual reassignment sweep is the control.
- **Rule 3, the recorded sweep.** Also `Notes`, also unreachable, and in
  any case a rule about a coordinator's process rather than about a row.
- **That a status is *true*.** A save rule proves a date and a sentence of
  evidence exist. Whether the practice they describe actually happens is
  what the assessment standard above, and its spot-check-don't-file-check
  instruction, is for.

**What the colours enforce, which is nothing, but they do it usefully.**
`ReviewDate` escalates to red once it is past on **every** row, including
*Not applicable* ones. Every other register in this theme suppresses that
escalation on its terminal status; this one has no terminal status,
because the cycles table above puts *Not applicable* on a review cycle for
the same reason it puts everything else on one — applicability is exactly
what changes.

## Lifecycle

Superseded obligations are retired in Notes (instrument repealed/replaced),
never deleted — the history shows duty-in-force at any date. Export before
decommission; never run `rollback.js.txt` against real rows.
