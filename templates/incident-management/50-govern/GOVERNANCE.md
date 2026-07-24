# Incident management — governance

## Ownership

| Role | Held by | Accountable for |
|---|---|---|
| Process owner | *(e.g. quality/safety/ops manager)* | Triage SLA, severity definitions, trend review, this document |
| IN Incident Handlers | The response team | Triage, resolution, corrective actions |
| All staff | — | Reporting what they see |

## Sector note — healthcare (and other regulated sectors)

This register is for **corporate and non-clinical** incidents. Clinical
incidents belong in your mandated clinical-incident system
(VHIMS/RiskMan-class in Victorian health; equivalents elsewhere) — never
here. Where a corporate incident touches a clinical event, record the
corporate substance and reference the clinical system's identifier; no
patient-identifiable detail enters this list. See
[templates/HEALTHCARE.md](../../HEALTHCARE.md).

## Severity definitions (edit to your context — then keep the enum in sync)

| Severity | Meaning | Triage SLA |
|---|---|---|
| Critical | Ongoing harm/loss, or imminent risk of it | Same business day |
| Major | Significant harm/loss occurred; contained | 1 business day |
| Moderate | Limited impact; process failed but recovered | 3 business days |
| Minor | Near-miss / no-impact observation | 5 business days |

## Review cadence

- **Daily** (handlers): Triage queue to zero within SLA.
- **Monthly** (process owner): trend review — incidents by category and
  severity; overdue corrective actions chased by name.
- **Quarterly**: sample 5 Closed incidents; check corrective actions were
  real (evidence in Notes), not paperwork.

## The "edit own report" question — honest options

SharePoint permission levels cannot grant "edit *your own* items only" —
that's an item-level setting, not a level. Your options:

1. **This template's default**: reporters cannot edit after submission —
   strongest evidential integrity; corrections go through handlers.
2. Site owners may enable the list's *item-level permissions* setting
   ("Create items and edit items that were created by the user") manually
   in List settings → Advanced — reporters can then amend their own reports.
   Deliberately not automated: it changes evidential meaning, so it should
   be an explicit governance decision recorded here.

## Data-quality rules

1. Every incident past Reported has a `Handler`.
2. `Resolved` requires `ResolvedDate`; `Closed` requires all linked actions
   terminal.
3. Reporter wording in `Detail` is never edited — handlers append.

## Lifecycle

Incident records are evidence: retain per your incident/records policy;
export before any decommission; never run `rollback.js` against real data.
