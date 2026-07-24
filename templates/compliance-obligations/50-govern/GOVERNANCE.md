# Compliance obligations — governance

## Ownership

| Role | Held by | Accountable for |
|---|---|---|
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
|---|---|
| Non-compliant / Partially compliant | Monthly until resolved |
| Compliant, high-stakes instruments (safety, funding conditions) | Annually |
| Compliant, other | Every 2 years |
| Accreditation standards | Aligned to your accreditation cycle, front-loaded before assessment visits |

## Reporting

- **Quarterly** to the executive/audit committee: the gap list with
  remediation status; counts by instrument; anything Not assessed older
  than 6 months.
- **Pre-accreditation**: the *By source* view for the relevant standard IS
  the self-assessment evidence index.

## Data-quality rules

1. No status other than Not assessed without LastAssessedDate + evidence.
2. Every row has a human Owner; leavers reassigned within a month.
3. Instrument changes trigger a recorded sweep (dated in Notes).

## Lifecycle

Superseded obligations are retired in Notes (instrument repealed/replaced),
never deleted — the history shows duty-in-force at any date. Export before
decommission; never run `rollback.js` against real rows.
