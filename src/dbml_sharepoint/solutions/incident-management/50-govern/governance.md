# Incident management — governance

## Ownership

| Role | Held by | Accountable for |
| --- | --- | --- |
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
[templates/healthcare.md](../../healthcare.md).

The seeded demo data holds nothing clinical, for the same reason.

## Severity definitions (edit to your context — then keep the enum in sync)

| Severity | Meaning | Triage SLA |
| --- | --- | --- |
| Critical | Ongoing harm/loss, or imminent risk of it | Same business day |
| Major | Significant harm/loss occurred; contained | 1 business day |
| Moderate | Limited impact; process failed but recovered | 3 business days |
| Minor | Near-miss / no-impact observation | 5 business days |

`Critical` is the one severity with a row-level signal: an open Critical
incident washes its whole row in the default view. That is deliberate
scarcity — one signal, reserved for the state that should interrupt
somebody's day. Renaming the member disables the wash silently, so keep the
enum and the mapping in step.

## Review cadence

- **Daily** (handlers): **Triage queue** to zero within SLA.
- **Monthly** (process owner): **Resolved last 90 days**, grouped by
  category, for the trend review; and **By owner** to chase overdue
  corrective actions by name.
- **Quarterly**: sample 5 Closed incidents in **By incident**; check
  corrective actions were real (evidence in Notes), not paperwork.

### Two limits on the numbers you quote

- **"Resolved last 90 days" is a rolling window, not a calendar quarter.**
  CAML has no calendar predicate. For a quarter-aligned figure, export.
- **The mean time to resolve is on the screen.** The view groups by
  category, collapsed, and averages `DaysToResolve`, so each category's
  figure and the overall one are both visible. A quarter-aligned figure
  still needs an export, because the window is a rolling ninety days.

## What is enforced at save, and what stays a governance check

| Enforced at save | Rule |
| --- | --- |
| All three incident dates, and an action's Done Date | None may be in the future |
| `Incident` list | **Resolved** or **Closed** needs a Resolved Date |
| `CorrectiveAction` list | **Done** needs a Done Date |

**Three rules below are stated as standards and cannot be formulas.** They
are listed here rather than left to be discovered by somebody trying:

- **Rule 1, every incident past Reported has a Handler.** SharePoint
  validation formulas cannot reference person columns at all — not as an
  operand, not as a null test. The structural half is that Handler is off
  the New form entirely, so it is a triage act by construction; the rest is
  the daily triage review.
- **Rule 2's second half, Closed requires all linked actions terminal.**
  The actions are on a different list, and a save rule reaches only its
  own. The **By incident** view is the reconciliation, and it exists for
  this: expand the incident, read its actions, then close it or don't.
- **A cancelled action says why in its Notes.** Notes is rich text, which
  validation formulas cannot reference either.

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

1. Every incident past Reported has a `Handler`. **Not enforceable — see
   above.**
2. `Resolved` requires `ResolvedDate` (**enforced at save**); `Closed`
   requires all linked actions terminal (**not enforceable — the By
   incident view is the control**).
3. Reporter wording in `Detail` is never edited — handlers append.
4. Every corrective action names one person, not a team. Not enforceable —
   `AssignedTo` is required, but a shared account satisfies a required
   field as happily as a person does.

## Lifecycle

Incident records are evidence: retain per your incident/records policy;
export before any decommission; never run `rollback.js.txt` against real data.
