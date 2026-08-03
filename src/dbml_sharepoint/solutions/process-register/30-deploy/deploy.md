# Deploying the process register (administrator)

Shared procedure: [`templates/README.md`](../../README.md) with
`<name> = process-register`. Run order: **assess** the target site (paste
`build/assess.js.txt`, read-only; the verdict must be COMPATIBLE or an accepted
DEGRADED) → **review** `build/deploy-manifest.md` (must show 0 validation
errors) → **paste** `build/deploy.js.txt` from a Site Owner's console → **verify**
against the checklist below. Template-specific notes follow.

## Before you build

- [ ] `PR_` prefix free on the target site.
- [ ] `CurrentState` values reflect your actual landscape (name legacy
      systems explicitly if it helps honest answers). If you change them,
      re-read **Key-person risk** in `mapping.yaml` — it filters on two
      of those members by name, and a rename empties the view without
      failing the build.
- [ ] The scoring definitions in `50-govern/governance.md` are agreed —
      scores are only comparable if everyone scores the same way.
- [ ] `Function` is free text, not an enum. Agree the function names
      **before** the first workshop: **By function** groups on this column,
      and "Corporate services", "Corp services" and "Corporate Services"
      group as three functions.
- [ ] Inventory workshops scheduled (see `40-adopt/staff-guide.md`) — an
      empty register deployed without a filling plan stays empty.
- [ ] The header shows `Process: <title>` on a saved row and `New process`
      before the title is typed, updating live. If you add another
      `[$FieldName]` reference, note that a **calculated** column always
      resolves empty in a form header — `DigitisationPriority` would show
      nothing there, with no error. Its value reaches the form through its
      own `column_formatting`, in the **System** body section.

## Optional: the seeded demonstration build

The score bar, the state colours and every declared view are invisible on
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
then `demo-data.js.txt`, from the same bundle. It creates six rows across four
functions, covering all five current states and all six digitisation
statuses, with two landing in **Key-person risk** — enough that every
declared view has content and every colour band renders.

**Delete the demo rows before active use.** Every demo Title begins with
`[DEMO] `, so they are obvious in every view, they are matched by Title on
re-paste (running it twice never duplicates), and `rollback.js.txt` treats a
list whose rows are *all* demo-marked as demo-only content. Do not seed a
site that already holds a real inventory.

## After the paste — verification checklist

- [ ] `PR_BusinessProcess` exists and all four declared views appear:
      **The worklist** (the default), **Programme dashboard**, **By
      function**, **Key-person risk**. If you seeded, none of them is
      empty. The generated **All Items** recovery view is hidden from the
      modern view bar because this template has an authored default.
- [ ] **Key-person risk** filters on two columns at once — high
      criticality **and** still on paper or in a spreadsheet. On the seeded
      build it returns the roster spreadsheet and the paper visitor book,
      which is the quarterly slide in two rows. `Pain notes` is on the
      view, because "only one person understands the award formulas" is
      the sentence leadership remembers, not the score.
- [ ] **Programme dashboard** groups by `DigitisationStatus`, collapsed,
      and carries `System URL`. Collapse to the **Digitised** group and a
      row with no link is an empty cell in a column of links — that is the
      compensating control for governance rule 3, which cannot be a save
      rule (see below).
- [ ] **By function** groups by `Function`, collapsed — the workshop and
      review unit.
- [ ] Score spot-checks on a test process:
      - High criticality + Severe pain → **DigitisationPriority = 9**
      - Medium + Moderate → **4**
      - Low + Minor → **1**
      - Clear Criticality → score goes **blank**, and the bar disappears
        rather than rendering at zero length.
- [ ] The score bar's fill comes from `Pain level`, not from the score: a
      severely painful process is red whatever its criticality drags the
      number down to. That is the fleet pattern — the bar and the band
      column beside it cannot disagree, because they read the same map.
      (The project pipeline's bar runs the opposite way, to green, because
      a tall bar there is an opportunity rather than a problem.)
- [ ] The **Review date** turns red once past due on a live row, and stays
      **plain** on the **Digitised** one even though it is 200 days past.
      That is the guard: a digitised process and one ruled out are both
      settled, and a date that keeps shouting after the decision trains
      people to ignore the colour.
- [ ] List Settings → Indexed columns shows `Function`,
      `DigitisationStatus` and `CurrentState`. The build manifest lists
      the same three. SharePoint cannot index the calculated
      `DigitisationPriority`, so the four views that sort by it are not
      guaranteed to scale past the list-view threshold.
- [ ] The New form shows **Name the process**, **Score it**, **Digitise
      it** and **Review**, each holding the fields named in
      `20-configure/formatting/businessprocess-form-body.json`. **System**
      is last and shows as a bare heading on the New form — it holds only
      the calculated `Digitisation Priority`, and calculated columns never
      render on entry forms. Cosmetic and expected.
- [ ] **The workshop form is short by design.** `Target state` and
      `System URL` are absent from a new row: `DigitisationStatus` defaults
      to **Not assessed**, and the workshop's job is to see, not to solve.
      Change the status to **Assessed** and `Target state` appears; change
      it to **In progress** and `System URL` appears too.
- [ ] **The save rule.** Set `DigitisationStatus` to **Planned** with
      `Target state` empty — refused. "Planned" with nowhere named is a
      status with no content, and the programme dashboard would be counting
      intentions.
- [ ] `Review date` refuses a date more than twelve months out, with its
      own message, because the inventory refresh is annual. Leave it blank
      and it saves — a row captured in a workshop and not yet given a
      review date is a normal intermediate state.
- [ ] Any Member can create and edit rows.
- [ ] Delete the test row.
- [ ] Even as an owner: changing a deployed column's type, choices or
      settings is refused (sealed) and List settings offers no "Delete
      this list"; a display-name rename is still possible — it is
      drift, reverted and reported at the next re-paste.

## Redeploying

Bump `schema_version`, rebuild, re-paste. Score-definition changes re-score
every row — recalibrate deliberately, not casually. The four declared views
are reconciled every run; views you create yourself are user content and
are never touched.
