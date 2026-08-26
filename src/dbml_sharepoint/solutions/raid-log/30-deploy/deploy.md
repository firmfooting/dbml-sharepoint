# Deploying the RAID log (administrator)

Shared procedure: [`templates/README.md`](../../README.md) with
`<name> = raid-log`. Run order: **assess** the target site (paste
`build/assess.js.txt`, read-only; the verdict must be COMPATIBLE or an
accepted DEGRADED) -> **review** `build/deploy-manifest.md` (must show 0
validation errors) -> **paste** `build/deploy.js.txt` from a Site Owner's
console -> **verify** against the checklist below. Template-specific notes
follow.

## Before you build

- [ ] `RAID_` prefix free on the target site.
- [ ] **One project per site.** These four lists carry no project column,
      because the site is the project. Two projects sharing a site share
      one risk log, one action list and one decision log, and no view can
      separate them afterwards. Deploy the family once per project site.
- [ ] **No list here will reach 5,000 rows.** The only limit that could
      matter is the list view threshold on lookup pickers, and it bites only
      past 5,000 items in the target list. A project RAID log is bounded by
      one project's life; a risk list approaching that has outgrown this
      template and belongs in risk-register. The `RelatedRisk` picker shows
      only live risks: its display column is the calculated `LiveRiskTitle`,
      blank for Closed, so it cannot be indexed and the picker depends on
      this list staying small. See `50-govern/governance.md`.
- [ ] `raid_issue_severity` and `raid_risk_response` match how your project
      actually talks. Severity drives the issue colours and the row wash;
      a member missing from the enum is a member nobody can choose.
- [ ] If your organisation has its OWN risk matrix, encode it in
      `mapping.yaml` **now**, before first deploy. The comment above
      `calculated_formulas` shows the cell layout; keep the DBML
      Likelihood and Consequence enums in the same order the formulas
      index them.
- [ ] Each header shows `Risk: <title>` / `Action: <title>` /
      `Issue: <title>` / `Decision: <title>` on a saved row, and
      `New risk` / `New action` / `New issue` / `New decision` before the
      title is typed, updating live. If you add another `[$FieldName]`
      reference, note that a **calculated** column always resolves empty in
      a form header: `ResidualRiskRating` and `RiskScore` show nothing
      there, with no error. Their values reach the form through their own
      `column_formatting`, in the body sections.

## Optional: the seeded demonstration build

The matrix, the row wash on an Extreme risk, the score bar, the overdue
colouring and the conditional date fields are all invisible on empty lists,
and a RAID log is judged in the first two minutes of the first project
meeting it appears in. To see it working, rebuild with `--seed`:

```bash
dbml-sharepoint build \
  --schema 10-design/schema.dbml \
  --mapping 20-configure/mapping.yaml \
  --release 20-configure/release.yaml \
  --site-url https://yourtenant.sharepoint.com/sites/your-site \
  --site-role default \
  --seed \
  --out ./build
```

That bundle contains an extra file, `demo-data.js.txt`. Paste
`deploy.js.txt` first, then `demo-data.js.txt`, from the same bundle. It
creates six risks spanning all four rating bands and both statuses (one of
them already past its review date, one Extreme, one Closed with a closure
note), six actions across every status including one overdue and still
open, five issues across every severity and every status, and four
decisions. Three actions and two issues carry a `RelatedRisk` pointing at a
demo risk, so the lookup demonstrates itself; the rest leave it blank,
which is the ordinary case.

**Paste order matters.** The demo actions and issues reference demo risks
by title, so `RAID_ProjectRisk` has to hold them first. One
`demo-data.js.txt` does the whole family in the right order; do not split
it.

**Delete the demo rows before active use.** Every demo Title begins with
`[DEMO]`, so they are obvious in every view, they are matched by Title on
re-paste (running it twice never duplicates), and `rollback.js.txt`
requires per-list confirmation before every delete. Do not seed a site that
already holds a real RAID log.

This family declares no URL column, so nothing here seeds a hyperlink. If
you add one, do not seed it: a SharePoint URL column takes a structured
value over REST rather than a bare string, and this repository does not
seed a write it has not read back from a live list.

## After the paste: verification checklist

- [ ] `RAID_ProjectRisk`, `RAID_ProjectAction`, `RAID_ProjectIssue` and
      `RAID_ProjectDecision` exist, Risk first (the other two lists look up
      to it).
- [ ] Display titles read **Project Risk**, **Project Action**, **Project
      Issue** and **Project Decision**. The internal names keep their
      unspaced form, which is what every view and the reporting bundle key
      on.
- [ ] All eleven declared views appear:
      - **Project Risk**: *Open* (the default), *Review due*, *Closed*.
      - **Project Action**: *Open by person* (the default, grouped by
        Assigned To and collapsed), *My actions*, *Overdue*, *Done and
        dropped*.
      - **Project Issue**: *Open* (the default), *By owner* (grouped and
        collapsed), *Resolved and closed*.
      - **Project Decision**: *Decision log* (the default).
      If you seeded, none of the eleven is empty. The generated **All
      Items** recovery view is hidden from the modern view bar on all four
      lists, because each has an authored default.
- [ ] **My actions** shows *your* open actions and changes per signed-in
      user. Ask a colleague to open it and confirm they see theirs, not
      yours. That is the whole test.
- [ ] List Settings -> Indexed columns shows `Status`, `RiskResponse` and
      `ReviewDate` on Project Risk; `Status`, `AssignedTo`, `DueDate` and
      `RelatedRisk` on Project Action; `Status`, `Severity`, `Owner`,
      `RaisedDate` and `RelatedRisk` on Project Issue; and `DecisionDate`
      on Project Decision. **`LiveRiskTitle` does not appear**, and that is
      correct: it is a calculated column and cannot be indexed. It is the
      `RelatedRisk` display column, and its being calculated is what blanks
      closed risks out of the picker. See the lookup note in
      `50-govern/governance.md`.
- [ ] Matrix spot-checks on a test risk:
      - Rare + Minor -> **Low / 1**
      - Unlikely + Substantial -> **Medium / 11**
      - Very Likely + Business Critical -> **Extreme / 24**
      - Almost Certain + Business Critical -> **Extreme / 25**
      - Clear Likelihood -> `ResidualRiskRating` and `RiskScore` both go
        **blank** (unrated is visible, not defaulted).
- [ ] The risk form shows **Describe the risk**, **Assess the risk**,
      **Response and owner**, **Review and closure** and **System**, in
      that order. **System** is last and holds only the two calculated
      matrix outputs, so they do not interrupt the assessment inputs. On
      Edit and Display both appear read-only and neither can be typed over.
- [ ] The action form shows **The action**, **Owner and date** and
      **Progress**. The issue form shows **Describe the issue**, **Severity
      and owner**, **Progress** and **Resolution and closure**. The
      decision form shows **The decision** and **Why**. Every column sits
      in one of them.
- [ ] The forms react as you fill them in:
      - **Closure Note** is absent from a new risk and from any Open one.
        Set Status to **Closed** and it appears.
      - **Completed Date** is absent from a new action and from any open
        one. Set Status to **Done** and it appears.
      - **Resolved Date** and **Resolution** are absent until Status is
        **Resolved** or **Closed**, on New as well as Edit. An issue that
        was raised, fixed and is only being written up afterwards is a real
        case, so setting the status at creation reveals both fields
        immediately.
      - Move any of those statuses back and the field hides again,
        **keeping whatever was typed**. SharePoint has no mechanism to
        clear it.
- [ ] Save rules, all four:
      - A **Completed Date** in the future is refused, with its own
        message.
      - A **Resolved Date** in the future is refused, with its own message.
      - Action Status **Done** with no Completed Date is refused, with the
        list's message.
      - Issue Status **Resolved** or **Closed** with no Resolved Date is
        refused, with the list's message.
      **Dropped** is deliberately not covered by any of them, see below.
- [ ] A closed risk with an empty **Closure Note** still saves. That is a
      governance check rather than a rule, because SharePoint validation
      formulas cannot read a rich-text column at all.
- [ ] Create a test risk, then an action and an issue against it: both
      `RelatedRisk` pickers offer the test risk by title.
- [ ] Leave `RelatedRisk` blank on another test action and another test
      issue. Both save. The link is optional on both lists.
- [ ] An open or in-progress action past its due date renders with the
      severe treatment and a warning icon. Close it Done or Dropped and the
      date goes plain. The same applies to an open risk past its review
      date; close the risk and the date goes plain.
- [ ] An Extreme risk washes its whole row in the *Open* view, and a
      Critical issue washes its whole row in the issue *Open* view. Nothing
      else does, on any list. One row-level signal per list is the whole
      budget.
- [ ] The action demands `AssignedTo` and `DueDate`, the issue demands
      `Owner` and `RaisedDate`, the risk demands `RiskOwner`, `Likelihood`,
      `Consequence` and `ReviewDate`, and the decision demands
      `DecisionDate` (all required).
- [ ] A new issue fills `Raised Date` with today automatically, and the
      date is still editable for something being recorded late.
- [ ] Any ordinary Member can create on all four lists (Contribute).
- [ ] Delete the test rows (action and issue first, then the risk).
- [ ] Even as an owner: changing a deployed column's type, choices or
      settings is refused (sealed) and List settings offers no "Delete this
      list"; a display-name rename is still possible. It is drift, reverted
      and reported at the next re-paste.

### Why "Dropped" carries no save rule

`50-govern/governance.md` asks for a note when an action is dropped, and
`40-adopt/staff-guide.md` says the same. Neither is enforced, on purpose.
Dropping an action is already the honest move against leaving it Open
forever, and a template whose first act is to make the honest move harder
than the dishonest one has its incentives backwards. **Done** is different:
a Done with no date is a claim, so it is refused.

### Why Project Decision ships one view and no colours

A decision has no lifecycle to filter on and no owner to group by. A second
view would be the same rows in a different order, and a colour would have
to mean something the column does not hold. A decision is a fact, which is
the point of the list.

## Redeploying: matrix change warning

Bump `schema_version`, rebuild, re-paste. Rows untouched; views, forms,
formatting and save rules reconciled to the declaration.

The exception is the matrix. A redeploy applies formula changes to the live
columns, and SharePoint then **recalculates every existing row**. That is
desirable for a typo fix and dangerous for a matrix revision. This template
drops risk-register's `MatrixVersion` guard, so there is nothing here to
stop a recalculation re-rating history silently. Export the risk list to
Excel before touching a cell, and read the matrix section of
`50-govern/governance.md` first.

## Enterprise reporting access

The deploy declares the `dbml Enterprise Readers` site group, shared with
every other family deployed to the site, and grants it `Read` on every list
in this family. The group starts empty only if no family has deployed to
the site yet; it gains a member when any family's build is run with
`--enterprise-reader <account>`, which enrols exactly that one account and
nothing else. `rollback.js.txt` does not remove it: rollback deletes lists,
not site groups or role assignments, so the group and any account enrolled
in it survive a rollback.

A later build that omits the flag does not put the group back to empty:
enrolment only runs when `--enterprise-reader` is given, so an account
enrolled by an earlier build, of this family or any other sharing the site,
keeps its membership and its `Read` grant on every list it was declared
against. Removing it is manual. Clear it in Site permissions > Groups.

If the group already holds anyone other than that account, the deploy
**aborts before enrolling** and removes nobody. Before you clear anyone
out, check who it is: the group is shared by every family on this site, so
the unexpected member is most likely **another family's reporting
account**, and removing it silently breaks that family's reporting. Agree
one reader account for the site and rebuild with that address, or rebuild
without the flag. Only clear the group in Site permissions > Groups once
you know nothing else needs the account.

On one Microsoft 365 group-connected Team Site (measured 2026-08-11) the
enrolled account ends up with the built-in `Read` on each list and
`Use Remote Interfaces` intact at web scope. Publishing sites, where
lockdown mode is on by default, and the reporting client's own list
enumeration are still unverified, so the end-to-end path (Power BI or any
other API client) is not yet proven. See the danger block in the mapping
reference's Security section.
