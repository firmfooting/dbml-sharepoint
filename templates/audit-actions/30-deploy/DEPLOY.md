# Deploying audit actions (administrator)

Shared procedure: [`templates/README.md`](../../README.md) with
`<name> = audit-actions`. Run order: **assess** the target site (paste
`build/assess.js`, read-only; the verdict must be COMPATIBLE or an accepted
DEGRADED) → **review** `build/deploy-manifest.md` (must show 0 validation
errors) → **paste** `build/deploy.js` from a Site Owner's console →
**verify** against the checklist below. Template-specific notes follow.

## Before you build

- [ ] `AU_` prefix free on the target site.
- [ ] `AuditType`/`FindingRating` enums match your assurance framework
      (many audit firms rate findings themselves — mirror their scale).
      **`FindingRating` is now colour-mapped**, Low → Critical, using the
      same four tokens as the risk register's rating columns; a renamed
      member strands old rows *and* silently loses its colour. If your
      scale has a different number of bands, edit the map in
      `mapping.yaml` at the same time as the enum.
- [ ] **Decide your closure-report horizon before first deploy.** The
      *Closed, last 90 days* view filters `ClosedDate ≥ today-90`. If your
      committee cycle is not quarterly, change the `today-90` in
      `mapping.yaml` now.
- [ ] You know who forms **AU Audit Coordinators**.
- [ ] The headers show `Audit: <title>` and `Recommendation: <title>` on
      saved rows, and `New audit` / `New recommendation` before the title
      is filled in, updating live as it is typed. If you add another
      `[$FieldName]` reference, note that a **calculated** column always
      resolves empty in a form header — `DaysLate` will show nothing there,
      with no error. Its value reaches the form through its own
      `column_formatting`, in the **System** section.

## Optional: the seeded demonstration build

The rating colours, the lateness bar and every declared view are invisible
on two empty lists. To see them working, rebuild with `--seed`:

```bash
dbml-sharepoint build \
  --schema templates/audit-actions/10-design/schema.dbml \
  --mapping templates/audit-actions/20-configure/mapping.yaml \
  --release templates/audit-actions/20-configure/release.yaml \
  --site-url https://yourtenant.sharepoint.com/sites/your-site \
  --site-role default \
  --seed \
  --out ./build
```

That bundle contains an extra file, `demo-data.js`. Paste `deploy.js`
first, then `demo-data.js`, from the same bundle. It creates five audits —
one per type — and six recommendations covering every status and every
finding rating, including the row that matters most for testing the
*Overdue* view: a recommendation whose **original** date has passed and
whose **revised** date has not, and which is therefore correctly *not*
overdue.

**Delete the demo rows before loading your backlog.** Every demo Title
begins with `[DEMO] `, so they are obvious in every view, they are matched
by Title on re-paste (running it twice never duplicates), and `rollback.js`
treats a list whose rows are *all* demo-marked as demo-only content.

## After the paste — verification checklist

- [ ] `AU_Audit` and `AU_Recommendation` exist (Audit first).
- [ ] **Audit** shows two declared views: **Recent reports** (the default)
      and **By type**. Two is the honest number: an audit row is a header
      record with no lifecycle and no deadline, so there is nothing to make
      a queue or a cadence lens out of. Everything with a clock or a state
      on it lives on the recommendations.
- [ ] **Recommendation** shows five: **Open by owner** (the default),
      **Overdue**, **Awaiting evidence**, **Committee pack**,
      **Closed, last 90 days**. If you seeded, none of them is empty. The
      generated **All Items** recovery views are hidden from the modern
      view bar because both lists have an authored default.
- [ ] **Overdue implements "(RevisedDue or DueDate) < today" properly.**
      Confirm with the demo data, or two test rows: a row with no revised
      date and a past due date **appears**; a row whose due date has passed
      but whose revised date is in the future **does not**. Those are two
      different branches of one filter, and getting the second wrong would
      re-surface every recommendation the extension mechanism exists to
      take out of the queue.
- [ ] **Closed, last 90 days** is a **rolling** ninety days, not "this
      quarter". CAML has no calendar-period predicate, so a
      quarter-boundary reading has to come from your own reporting; the two
      differ on the first day of a quarter and anyone reconciling a
      committee pack will notice.
- [ ] **Committee pack ships grouped by audit and sorted by committed
      date, not sorted by finding rating.** The old *Recommended views*
      table asked for the rating sort, and SharePoint cannot do it: a
      Choice column orders by its stored text, so "descending" would give
      Moderate, Low, High, Critical — not severity order, and worse than no
      rating sort because it looks like one. Severity is carried by the
      colours on the `FindingRating` column instead. If you need a true
      rating sort, the workaround is to number the choice members
      (`1 Low`, `2 Moderate`, …) in `10-design/schema.dbml` **before first
      deploy** — renaming them afterwards strands existing rows.
- [ ] `DaysLate` renders as a bar whose **fill colour comes from
      `FindingRating`**, so a forty-day-late Critical and a forty-day-late
      Low read differently at the same bar length.
- [ ] List Settings → Indexed columns shows `AuditType` and `ReportDate`
      on Audit, and `Status`, `Audit`, `Owner`, `DueDate` and
      `FindingRating` on Recommendation. The build manifest lists the same
      seven.
- [ ] The Audit New form shows **The review** and **Response**. The
      Recommendation New form shows **The finding**, **The agreed action**
      and **Closure**. **System** is last on Recommendation and holds
      `DaysLate` only — it is calculated, so on the New form that section
      is a bare heading with nothing under it. That is cosmetic and
      expected; on Edit and Display the value appears there, read-only.
- [ ] **Form behaviour** (declared in `mapping.yaml` under
      `form_visibility:`): on the *New* form, RevisedDue, ClosedDate and
      EvidenceUrl are all absent. Save the row, reopen it for edit:
      RevisedDue is now there; ClosedDate and EvidenceUrl are still hidden.
      Set Status to *Implemented - awaiting evidence* — EvidenceUrl appears
      as you change the value, without saving. Set it to *Closed* —
      ClosedDate appears too.
- [ ] **Both endings need a ClosedDate** (`list_validation:`). With Status
      *Closed* and ClosedDate empty, saving is refused — `DaysLate` is
      computed from that date, so without it the committee's lateness
      figure is simply blank. Fill it; it saves. **Then try the same with
      *Risk accepted***: also refused, and for a sharper reason. That
      status leaves the default and Overdue queues the way a closure does,
      and **Closed, last 90 days** — the committee's closure report —
      filters on `ClosedDate`, which a blank cannot satisfy. Without the
      rule, an accepted recommendation would be in no queue and in no
      report.
- [ ] **The EvidenceUrl requirement is NOT a save rule**, and you should
      confirm that rather than assume it: set Status to *Closed* with
      EvidenceUrl empty and a ClosedDate filled, and the row **saves**.
      SharePoint does not permit the alternative — a validation formula
      referencing a URL column is refused when you try to set it, with
      *"One or more column references are not allowed, because the columns
      are defined as a data type that is not supported in formulas."* The
      build refuses the operand for that reason, so a template carrying
      such a rule fails at build rather than partway through your paste.
      Evidence at closure remains a criterion in
      `50-govern/GOVERNANCE.md`, and the **Closed, last 90 days** view
      shows the column so an empty one is visible to the committee.
- [ ] **Two per-column save rules**, each with its own message: a future
      `ReportDate` on an audit, and a future `ClosedDate` on a
      recommendation. The second matters more than it looks: `DaysLate`
      guards against negative ranges by returning 0, so a recommendation
      closed "next month" would report as closed **on time**, silently, on
      the exact number the audit committee reads.
- [ ] Hidden ≠ inaccessible. Confirm a hidden column still holds its value:
      the reporting bundle's data dictionary lists all three, and a view
      can show them. `form_visibility` governs forms only.
- [ ] DaysLate spot-checks: Due `2026-07-01` + Closed `2026-07-10` → **9**;
      Closed `2026-06-28` (early) → **0**; add RevisedDue `2026-07-15`,
      Closed `2026-07-20` → **5**.
- [ ] Ordinary Members: read-only.
- [ ] **Load the backlog**: every open recommendation from existing audits
      goes in now — a partial register is worse than none, because it looks
      complete.
- [ ] Populate **AU Audit Coordinators**; delete the test rows.
- [ ] Even as an owner: changing a deployed column's type, choices or
      settings is refused (sealed) and List settings offers no "Delete
      this list"; a display-name rename is still possible — it is
      drift, reverted and reported at the next re-paste.

## What is not enforced at save

- **The recorded authority behind a *Risk accepted* ending.** It lives in
  `Notes`, which is rich text, and a SharePoint validation formula cannot
  reference a multi-line column at all. `50-govern/GOVERNANCE.md` names who
  may accept a risk; the register cannot check that they did.
- **That the evidence link is actually evidence.** The save rule proves a
  URL is present. Only a coordinator reading it proves it demonstrates the
  action — which is what the *Awaiting evidence* view exists for, and why
  the staff guide says a link to a folder is not evidence.
- **The ten-business-day loading rule.** A rule about a habit, not a row.

One caveat on the evidence rule itself, recorded rather than hidden: it
puts a **hyperlink** column inside a SharePoint validation formula. This
template has shipped that rule since before the family standard existed and
it is kept, but it has not been read back from a live tenant, and
`grants-register` declined to copy the pattern for that reason. The
checklist item above is how you find out on your own tenant, on the first
row you close — if the save is *not* refused with EvidenceUrl empty, tell
us, and treat the closure-evidence standard as a governance check until it
is settled.

## Redeploying

Bump `schema_version`, rebuild, re-paste. Existing rows are untouched;
drifted settings are reconciled, and declared views are reconciled to the
declaration — a view retitled by hand comes back under its declared title.
