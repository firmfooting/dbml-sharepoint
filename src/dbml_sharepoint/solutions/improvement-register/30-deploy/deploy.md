# Deploying the improvement register (administrator)

Shared procedure: [`templates/README.md`](../../README.md) with
`<name> = improvement-register`. Run order: **assess** the target site
(paste `build/assess.js.txt`, read-only; the verdict must be COMPATIBLE or an
accepted DEGRADED) → **review** `build/deploy-manifest.md` (must show 0
validation errors) → **paste** `build/deploy.js.txt` from a Site Owner's console
→ **verify** against the checklist below. Template-specific notes follow.

## Before you build

- [ ] `CI_` prefix free on the target site.
- [ ] `Source` enum matches the registers you actually run (complaints,
      incidents, audits, measures, the process inventory) — the feeding
      loops in governance depend on it, and **By source** groups on it.
- [ ] Someone owns the fortnightly triage (governance) — an untriaged
      suggestion box curdles fast.
- [ ] The **180-day** full bar on `DaysIdeaToOutcome` matches what you
      consider a runaway cycle. It is set from the test discipline in
      `50-govern/governance.md` — one team, one fortnight, small before
      big — so two quarters from idea to outcome pins the bar. Change
      `max:` in `mapping.yaml` before first deploy if your cycles are
      honestly longer.
- [ ] The header shows `Improvement: <title>` on a saved row and `New
      improvement` before the title is typed, updating live. If you add
      another `[$FieldName]` reference, note that a **calculated** column
      always resolves empty in a form header — `DaysIdeaToOutcome` would
      show nothing there, with no error. Its value reaches the form through
      its own `column_formatting`, in the **System** body section.

## Optional: the seeded demonstration build

The stage colours, the cycle-time bar and every declared view are invisible
on an empty list. To see them working, rebuild with `--seed`:

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
stage, from five different sources, including two adoptions (one inside the
rolling ninety-day window and one outside it) and one abandoned test whose
lesson is written down.

**Delete the demo rows before active use.** Every demo Title begins with
`[DEMO] `, so they are obvious in every view, they are matched by Title on
re-paste (running it twice never duplicates), and `rollback.js.txt` treats a
list whose rows are *all* demo-marked as demo-only content. Do not seed a
site that already holds real improvements.

## After the paste — verification checklist

- [ ] `CI_Improvement` exists and all five declared views appear: **In
      flight** (the default), **Triage**, **Adopted this quarter**, **The
      learning shelf**, **By source**. If you seeded, none of them is
      empty. The generated **All Items** recovery view is hidden from the
      modern view bar because this template has an authored default.
- [ ] **"Adopted this quarter" is a rolling ninety days, not a calendar
      quarter.** CAML has no calendar-quarter predicate, so the view filters
      `AdoptedDate ≥ today-90`. The two differ on the first day of a
      quarter, and someone reconciling the quarterly slide against a
      committee pack will notice — this is the substitution, stated. If you
      need calendar quarters exactly, export and pivot rather than trusting
      the view.
- [ ] On the seeded build, **Adopted this quarter** shows one of the two
      adopted rows and not the other. That is the filter filtering: the
      second was adopted 160 days ago.
- [ ] **In flight** groups by `Owner`, collapsed — the fortnightly
      conversation is per owner before it is per improvement.
- [ ] **The learning shelf** is still called that. The staff guide asks
      people to celebrate what is on it; a view called "Abandoned" would
      argue the other way in the navigation bar. Both measures are on it,
      because an abandoned test where the number did not move is only a
      lesson when the two numbers sit side by side.
- [ ] **By source** is unfiltered on purpose — the quarterly question is
      whether the loops are real, and that is the size of each group across
      the whole register.
- [ ] Raised `2026-07-01` + Adopted `2026-08-15` →
      **DaysIdeaToOutcome = 45**, rendered as a bar a quarter of the way
      across. On the seeded build the 240-day cycle pins at full width.
- [ ] The bar is **not** coloured by stage. That is deliberate: the fleet
      rule takes a bar's fill from the rating column beside it, and nothing
      beside this one is a rating. Colouring it from Stage would repeat the
      Stage chip two columns away and say nothing about the number.
- [ ] List Settings → Indexed columns shows `Stage`, `Source`, `Owner` and
      `RaisedDate`. The build manifest lists the same four.
- [ ] The New form shows **The idea**, **Plan the test** and **Test and
      outcome**, each holding the fields named in
      `20-configure/formatting/improvement-form-body.json`. **System** is
      last and shows as a bare heading on the New form — it holds only the
      calculated `Days Idea to Outcome`, and calculated columns never
      render on entry forms. Cosmetic and expected.
- [ ] `MeasureBefore` is **required** and is on the New form — the form
      demands a baseline, which is deliberate and is the one field the
      whole register turns on.
- [ ] **Raising an idea is a five-minute job**, and the New form says so:
      `Benefit type`, `Test notes`, `Measure after` and `Adopted date` are
      all absent from it.
- [ ] The form reacts as you fill it in. On an existing row, set `Stage` to
      **Testing** and `Measure after` appears; set it to **Adopted** and
      `Adopted date` appears too. Switching back to **Idea** hides them
      again, keeping whatever was typed — SharePoint has no mechanism to
      clear a value on hide.
- [ ] **The two save rules**, sharing one message because a list has a
      single validation formula. Set `Stage` to **Abandoned** with `Adopted
      date` empty — refused. Set it to **Adopted** with `Measure after`
      empty — refused, same message. "Improved" has to be a number, and
      this is where that stops being a slogan.
- [ ] `Raised date` and `Adopted date` each refuse a future date, each with
      their own message. The median cycle time is a quarterly report line
      computed from those two dates and nothing else.
- [ ] Any Member can create and edit rows.
- [ ] Delete the test row.
- [ ] Even as an owner: changing a deployed column's type, choices or
      settings is refused (sealed) and List settings offers no "Delete
      this list"; a display-name rename is still possible — it is
      drift, reverted and reported at the next re-paste.

## Redeploying

Bump `schema_version`, rebuild, re-paste. The five declared views are
reconciled every run; views you create yourself are user content and are
never touched.

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
**aborts before enrolling** and removes nobody — clear it in Site
permissions > Groups and paste again, or rebuild without the flag.

On one Microsoft 365 group-connected Team Site (measured 2026-08-11) the
enrolled account ends up with the built-in `Read` on each list and
`Use Remote Interfaces` intact at web scope. Publishing sites — where
lockdown mode is on by default — and the reporting client's own list
enumeration are still unverified, so the end-to-end path (Power BI or any
other API client) is not yet proven. See the danger block in the mapping
reference's Security section.
