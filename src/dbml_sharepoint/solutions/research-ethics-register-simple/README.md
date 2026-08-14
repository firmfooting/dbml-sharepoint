# Research ethics register (single list)

One row per research or quality project referred to a partner HREC, with
ethics approval and site authorisation as two separate gates. For a health
service that has no ethics committee of its own. Deploys as one list:
`RG_Project`.

**The value case.** A health service with no ethics committee of its own
still does research and quality improvement. It sends those projects to a
partner service's or a university's HREC, and then has to answer a question
no spreadsheet answers well:

> This project is approved. Can it actually start **here**?

Ethics approval and site authorisation are two decisions by two authorities.
A project the partner HREC approved still cannot begin until this service's
research governance officer has assessed it and the Chief Executive or
delegate has authorised it for the site. The gap between those two events is
where somebody starts recruiting who should not, and it is invisible unless
something watches. This register watches: two independent status columns, two
form sections, a calculated **Site Readiness** column that collapses the pair
into one answer, and a row wash on the one combination that is genuinely
dangerous — a project that has started here (*Underway*, or *Closed to
recruitment* having been Underway first) with no site authorisation.

## Why one list, and what that costs

The obvious shape for this domain is three lists: a project, its amendments,
its progress reports, joined by Lookups. This template deliberately does not
ship that, for a reason measured on a live tenant rather than assumed.

**A SharePoint Lookup picker cannot be filtered.** The field has no filtering
attribute; the calculated-column workaround that community guidance
recommends is refused past 5,000 items; and the target list's own default
view filter is ignored by the picker. All three were tested and all three are
closed — see *SharePoint cannot filter a lookup* in the tool's
`reference/mapping.md`.

A project register is an **accumulator**: it only grows. By year three, an
amendment form's project picker offers every long-closed project alongside
the live one, and staff cannot find theirs. This is not the 5,000-item
threshold — 5 to 30 new projects a year never approaches it. It is picker
usability, and there is no fix inside a list schema.

The insight the design turns on: **filtering works everywhere in SharePoint
except a lookup picker.** Remove the child lists and the accumulation problem
becomes one SharePoint solves well — a default view filtered to live
projects. That is what *Project Stage* and the **Live projects** view do, and
they are load-bearing rather than housekeeping.

**What is genuinely lost**, stated plainly rather than discovered later:

- **No per-amendment and no per-report rows.** You cannot query "which
  projects filed late in 2025", and you cannot report on reporting timeliness
  across the portfolio.
- **Two simultaneous in-flight amendments are not representable.** The row
  holds the *latest* amendment's reference, status and date; a second one
  overwrites the first in those columns and survives only in Governance Notes
  and version history.
- **No per-report link.** The register records that a report is due and when
  the last one went, not where each one is filed.

The partner HREC holds the authoritative file either way, which is what makes
the trade acceptable for the service this template is for.

**When to build the multi-list shape instead:** a service running many
concurrent projects with frequent amendments, or one with its own research
office and a reporting obligation across a portfolio. That shape is a project
list with an amendment list and a progress-report list joined by Lookups, and
it answers the portfolio questions this one cannot. If that is you, take the
picker problem knowingly — curate the parent list, or build the picker
outside a list schema. This template will not pretend the lookup can be
filtered.

## What you get

Six views that **deploy with the list**: *Live projects* (the default —
closed work filtered away), *Ready to start here*, *Ethics cleared, not
authorised*, *Response required*, *Reports due soon* and *Archive*. The
two gates are two Choice columns and two form sections, never merged.
`SiteReadiness` is calculated from both and costs no join, because both live
on this one list. Build with `--seed` and six demo rows show every view and
every colour working before you type a thing — one of them deliberately
wrong, so you can watch the register catch it.

**Project metadata only. No participant data at any grain** — not names, not
identifiers, not recruitment counts. See `50-govern/governance.md`.

**Work the folders in order:**

| Step | Folder | You |
| --- | --- | --- |
| 1 | `10-design/` | Trim/rename columns and choice values to your vocabulary |
| 2 | `20-configure/` | Set your prefix if `RG_` collides; review the security model |
| 3 | `30-deploy/` | Administrator: build, paste, verify |
| 4 | `40-adopt/` | Circulate the staff guide to whoever records decisions |
| 5 | `50-govern/` | Agree the two sweeps, the owners and the data-quality rules |

**Customisation points:** the `ethics_pathway` and `authorisation_status`
members, to match your partner committee's and your own vocabulary; the
sixty-day window on *Reports due soon*; and the amendment-count data bar's
maximum. Delegations, fees and turnaround times are policy, not schema — see
`50-govern/governance.md`.
