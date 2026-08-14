# Deploying the project pipeline (administrator)

Shared procedure: [`templates/README.md`](../../README.md) with
`<name> = project-pipeline`. Run order: **assess** the target site (paste
`build/assess.js.txt`, read-only; the verdict must be COMPATIBLE or an accepted
DEGRADED) → **review** `build/deploy-manifest.md` (must show 0 validation
errors) → **paste** `build/deploy.js.txt` from a Site Owner's console → **verify**
against the checklist below. Template-specific notes follow.

## Before you build

- [ ] `PP_` prefix free on the target site.
- [ ] `CostBand` thresholds match your delegations; `Stage` names match how
      your organisation actually gates work.
- [ ] The gate authority table in `50-govern/governance.md` is agreed.
- [ ] If you change the `Stage` enum, re-read every `where:` in
      `mapping.yaml` — five declared views filter on stage names, and a
      renamed member makes a view silently return nothing rather than
      failing the build.
- [ ] The header shows `Proposal: <title>` on a saved row and `New
      proposal` before the title is typed, updating live. If you add
      another `[$FieldName]` reference, note that a **calculated** column
      always resolves empty in a form header — `PriorityScore` would show
      nothing there, with no error. Its value reaches the form through its
      own `column_formatting`, in the **System** body section.

## Optional: the seeded demonstration build

The score bar, the stage colours and every declared view are invisible on
an empty list. To see them working, rebuild with `--seed`:

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

That bundle contains an extra file, `demo-data.js.txt`. Paste `deploy.js.txt` first,
then `demo-data.js.txt`, from the same bundle. It creates six rows — one per
live stage plus a declined one and a delivered one — enough that every
declared view has content and every benefit, feasibility and cost band
renders. One of them is deliberately left at **Idea** with nothing scored,
so you can see an unscored proposal show a *blank* score rather than a low
one.

**Delete the demo rows before active use.** Every demo Title begins with
`[DEMO]`, so they are obvious in every view, they are matched by Title on
re-paste (running it twice never duplicates), and `rollback.js.txt` treats a
list whose rows are *all* demo-marked as demo-only content. Do not seed a
site that already holds real proposals.

## After the paste — verification checklist

- [ ] `PP_Proposal` exists and all five declared views appear: **The
      funnel** (the default), **Decision queue**, **Portfolio**,
      **Graveyard**, **Delivered**. If you seeded, none of them is empty.
      The generated **All Items** recovery view is hidden from the modern
      view bar because this template has an authored default.
- [ ] **Two changes from the "Recommended views" table this file used to
      carry**, both deliberate:
      - **The funnel** excludes **Parked** as well as Delivered and
        Declined. The table said Delivered/Declined only, which counted
        every parked proposal in both the live funnel and the Graveyard —
        and the funnel counts are what the pipeline owner reports monthly.
      - **Delivered** is a new fifth view. Under the old table a delivered
        proposal fell out of every recommended view the moment it was
        finished, so the one thing a pipeline exists to produce was the one
        thing it could not show.
- [ ] **The funnel** groups by `Stage`, expanded, and sorts by score
      within each group.
- [ ] **Portfolio** groups by `Sponsor`, collapsed — the quarterly
      capacity read is per sponsor before it is per project.
- [ ] **Graveyard** is still called Graveyard. Governance schedules an
      annual read-through of it; a view named "Closed proposals" would not
      get one. `Decision notes` is on it, because an unannotated graveyard
      is a list of dates.
- [ ] Score spot-checks on a test proposal:
      - Benefit High + Feasibility Easy → **PriorityScore = 9**
      - Benefit Medium + Feasibility Moderate → **4**
      - Benefit Low + Feasibility Hard → **1**
      - Clear Benefit → score goes **blank** (unscored is visible), and
        the bar disappears rather than rendering at zero length.
- [ ] The score bar's fill comes from `Benefit`, not from the score: a
      High-benefit proposal is green whatever its feasibility drags the
      number down to. That is the fleet pattern — the bar and the band
      column beside it cannot disagree, because they read the same map.
- [ ] List Settings → Indexed columns shows `Stage` and `ProposedDate`.
      The build manifest lists the same two. SharePoint cannot index the
      calculated `PriorityScore`, so the two views that sort by it are not
      guaranteed to scale past the list-view threshold.
- [ ] The New form shows **The idea**, **Scoping** and **Decision and
      delivery**, each holding the fields named in
      `20-configure/formatting/proposal-form-body.json`. **System** is last
      and shows as a bare heading on the New form — it holds only the
      calculated `Priority Score`, and calculated columns never render on
      entry forms. Cosmetic and expected.
- [ ] **Ideas are welcome half-formed**, and the New form says so:
      `Sponsor`, `Decision date`, `Decision notes` and `Delivered date` are
      all absent from it. A proposer writes the problem and the outcome.
- [ ] The form reacts as you fill it in. On an existing proposal, set
      `Stage` to **Declined** and `Decision date` and `Decision notes`
      appear; set it to **Delivered** and `Delivered date` appears instead.
      Switching back hides them again, keeping whatever was typed —
      SharePoint has no mechanism to clear a value on hide.
- [ ] **The three chained save rules**, sharing one message because a list
      has a single validation formula. Try each: set `Stage` to **Ready for
      decision** with `Benefit` blank; set it to **Approved** with
      `Decision date` blank; set it to **Delivered** with `Delivered date`
      blank. All three are refused, all three show the same message naming
      all three checks — that is the platform limit, not a defect, and it
      is why a rule reading only its own column belongs in
      `column_validation` where it keeps its own message.
- [ ] `Proposed date` and `Decision date` each refuse a future date, each
      with their own message. Time-in-stage is a monthly report line
      counted from those dates.
- [ ] Any Member can create and edit proposals.
- [ ] **Load the known backlog** — the wish-list everyone half-remembers
      goes in as Idea/Scoping rows now, or the pipeline starts life
      incomplete and stays that way.
- [ ] Delete the test row.
- [ ] Even as an owner: changing a deployed column's type, choices or
      settings is refused (sealed) and List settings offers no "Delete
      this list"; a display-name rename is still possible — it is
      drift, reverted and reported at the next re-paste.

## Redeploying

Bump `schema_version`, rebuild, re-paste. Changing the scoring formula
re-scores every row instantly — treat score changes as a governance event.
The five declared views are reconciled every run; views you create yourself
are user content and are never touched.

## Enterprise reporting access

The deploy declares the `dbml Enterprise Readers` site group — shared with every
other family deployed to the site — and grants it `Read` on every list in this
family. The group starts empty only if no family has deployed to the site yet;
it gains a member when any family's build is run with `--enterprise-reader
<account>`, which enrols exactly that one account and nothing else.
`rollback.js.txt` does not remove it: rollback deletes lists, not site groups
or role assignments, so the group and any account enrolled in it survive a
rollback.

A later build that omits the flag does not put the group back to empty:
enrolment only runs when `--enterprise-reader` is given, so an account enrolled
by an earlier build — of this family or any other sharing the site — keeps its
membership and its `Read` grant on every list it was declared against. Removing
it is manual — clear it in Site permissions > Groups.

If the group already holds anyone other than that account, the deploy
**aborts before enrolling** and removes nobody. Before you clear anyone out,
check who it is: the group is shared by every family on this site, so the
unexpected member is most likely **another family's reporting account**, and
removing it silently breaks that family's reporting. Agree one reader account
for the site and rebuild with that address, or rebuild without the flag. Only
clear the group in Site permissions > Groups once you know nothing else needs
the account.

On one Microsoft 365 group-connected Team Site (measured 2026-08-11) the
enrolled account ends up with the built-in `Read` on each list and
`Use Remote Interfaces` intact at web scope. Publishing sites — where
lockdown mode is on by default — and the reporting client's own list
enumeration are still unverified, so the end-to-end path (Power BI or any
other API client) is not yet proven. See the danger block in the mapping
reference's Security section.
