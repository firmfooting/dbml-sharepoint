# Research ethics register

*Theme: governance, risk & compliance — built for a health service that sends
its research and quality projects to somebody else's HREC*

Every project sent to an external ethics committee, and whether it has also
been authorised to run here. Two gates, never merged. Three lists:
`RG_Project` (each research, quality-improvement, audit or evaluation project,
its ethics decision **and** its site authorisation), `RG_Amendment` (each
change to an approved project, and what this site still has to do about it)
and `RG_ProgressReport` (each report owed to the committee, and whether it has
been acknowledged).

**The value case.** A health service with no committee of its own still does
research. It sends projects to a partner service's or a university's Human
Research Ethics Committee, and then has to answer a question no spreadsheet
answers well:

> This project is approved. Can it actually start **here**?

Ethics approval and site authorisation are two different decisions by two
different authorities. A project approved by an external HREC still cannot
begin until this service's own research governance officer has assessed it and
the Chief Executive or delegate has authorised it for the site. The gap
between those two events is where somebody starts recruiting who should not
be, and it is invisible unless something is watching for it. This register
watches: a calculated **Site Readiness** column reads both gates and says
`Ready to start here`, `Ethics cleared - site authorisation outstanding` or
`Site authorised - ethics not cleared`, and a project whose stage says it is
underway without authorisation has its whole row washed red.

The register also holds the obligations that follow approval, which are the
ones people forget: annual progress reporting, on which continued approval
depends; amendments, which need the committee's approval **and**, often, the
site's again; conditions of approval, which are not the same thing as the
approval; and the expiry date nobody diarised.

**Australian vocabulary throughout** — HREC, SSA, site authorisation, NHMRC,
the National Statement, low and negligible risk review. Every regulatory claim
the documents make carries its source; see `50-govern/governance.md`.

**Deploys with:** fourteen views (current projects with both gates side by
side, approved-but-not-authorised, approvals expiring, conditions outstanding
and closed; amendments grouped into a per-project file, with the committee,
approved-but-not-cleared-locally and decided; reports outstanding, per project,
due in 60 days, information requested and filed), sectioned forms on all three
lists, a calculated readiness answer that costs no lookup, three deadline dates
that turn red past due, one row wash on a project running without site
authorisation, eight save rules, and sixteen demo rows.

**Boundary:** this register holds **project metadata only** — no participant
data of any kind, not even aggregate recruitment counts. It records that a
report was made and links where it is filed; the report itself lives in your
records system. Read `50-govern/governance.md` before adding a column.

**Work the folders in order:**

| Step | Folder | You |
|---|---|---|
| 1 | `10-design/` | Fit the pathway, type and status choices to your jurisdiction |
| 2 | `20-configure/` | Prefix; governance-maintains, staff-read model |
| 3 | `30-deploy/` | Administrator: build, paste, verify; load the live projects |
| 4 | `40-adopt/` | Investigators and the governance officer; what each must do |
| 5 | `50-govern/` | Who authorises, the two sweeps, the sources, and the boundary |

**Customisation points:** the `ethics_pathway`, `ethics_status` and
`authorisation_status` enums, which are the most jurisdiction-specific thing
here; the 90-day expiry window and the 60-day report window, each of which
lives once, in its view; and whether your service treats a quality-improvement
activity as needing site authorisation at all.
