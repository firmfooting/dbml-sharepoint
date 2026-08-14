# Deploying the change register (administrator)

Shared procedure: [`templates/README.md`](../../README.md) with
`<name> = change-register`. Run order: **assess** the target site (paste
`build/assess.js.txt`, read-only; the verdict must be COMPATIBLE or an accepted
DEGRADED) → **review** `build/deploy-manifest.md` (must show 0 validation
errors) → **paste** `build/deploy.js.txt` from a Site Owner's console → **verify**
against the checklist below. Template-specific notes follow.

## Before you build

- [ ] `CH_` prefix free on the target site.
- [ ] `ChangeType` choices cover what your organisation actually changes.
- [ ] The decision-authority table in `50-govern/governance.md` is agreed —
      the register records approvals; the table is what makes them mean
      something.
- [ ] The SLA numbers in that table match the **21-day** full bar on
      `DaysToDecision` in `mapping.yaml`. It is set from the slowest
      authority level (15 business days ≈ three calendar weeks); if your
      slowest SLA is different, change `max:` before first deploy or the
      bar reads against a line nobody agreed.
- [ ] The header shows `Change: <title>` on a saved row and `New change`
      before the title is typed, updating live. If you add another
      `[$FieldName]` reference, note that a **calculated** column always
      resolves empty in a form header — `DaysToDecision` would show
      nothing there, with no error. Its value reaches the form through its
      own `column_formatting`, in the **System** body section.

## Optional: the seeded demonstration build

The five declared views, the impact and urgency colours, and the
decision-time bar are all invisible on an empty list. To see them working,
rebuild with `--seed`:

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
then `demo-data.js.txt`, from the same bundle. It creates six rows — two waiting
in the triage queue, one under review, one approved and stalled past sixty
days, one emergency decided in a day, and one rejected after three weeks —
enough that every declared view has content and every impact and urgency
band renders.

**Delete the demo rows before active use.** Every demo Title begins with
`[DEMO]`, so they are obvious in every view, they are matched by Title on
re-paste (running it twice never duplicates), and `rollback.js.txt` treats a
list whose rows are *all* demo-marked as demo-only content. Do not seed a
site that already holds real requests.

## After the paste — verification checklist

- [ ] `CH_ChangeRequest` exists; custom level **CH Submit Only** exists
      (Site settings → Permission levels).
- [ ] All five declared views appear: **In flight** (the default),
      **Triage queue**, **Awaiting decision**, **Approved, not yet
      implemented**, **Decision log**. If you seeded, none of them is
      empty. The generated **All Items** recovery view is hidden from the
      modern view bar because this template has an authored default.
- [ ] **Awaiting decision** groups by `Approver`, collapsed — the first
      thing you see is who you are chasing.
- [ ] **Approved, not yet implemented** sorts oldest decision first, so
      governance rule 2's stalled approvals (past 60 days) sit at the top.
      That rule is a monthly-review judgement, not a save rule; the sort is
      what makes it cheap to make.
- [ ] **Decision log** shows `Days to Decision` as a bar coloured by
      urgency. On the seeded build the Emergency change is a short red bar
      (one day) and the Routine rejection a long grey one (twenty-one
      days) — the same column saying two different things about the same
      number, which is the point.
- [ ] List Settings → Indexed columns shows `Status`, `ChangeType`,
      `Impact` and `RequestedDate`. The build manifest lists the same four.
- [ ] RequestedDate `2026-07-01` + DecisionDate `2026-07-10` →
      **DaysToDecision = 9**.
- [ ] The New form shows **Describe the change**, **Triage** and
      **Decision and implementation**, each holding the fields named in
      `20-configure/formatting/changerequest-form-body.json`. **System** is
      last and shows as a bare heading on the New form — it holds only the
      calculated `Days to Decision`, and calculated columns never render on
      entry forms. Cosmetic and expected.
- [ ] **The New form matches the submit-only intake.** `Impact`, `Status`,
      `Approver`, `Decision date`, `Decision notes` and `Implemented date`
      are all absent from it; a requester describes the change and says how
      urgent it is, and nothing else. `Status` defaults to **Submitted**,
      so a submitter cannot approve their own change.
- [ ] The form reacts as you fill it in. On an existing request, set
      `Status` to **Approved** and `Decision date` and `Decision notes`
      appear; set it to **Implemented** and `Implemented date` appears
      instead. Switching back hides them again, keeping whatever was
      typed — SharePoint has no mechanism to clear a value on hide.
- [ ] **The two save rules, and the two that could not be.** Set `Status`
      to **Approved** with `Decision date` empty — refused. Set it to
      **Implemented** with `Implemented date` empty — refused, same
      message, because a list has one validation formula and every
      cross-column rule shares it. Then set `Status` to **Rejected** and
      then **Closed** with no implemented date — that *saves*, deliberately:
      a rejected change is closed without ever being implemented.
- [ ] `Requested date` and `Decision date` each refuse a future date, each
      with their own message. Those two rules read only their own column,
      so they live in `column_validation` where they keep their own
      wording — and they matter because `Days to Decision` is computed from
      those two dates and nothing else.
- [ ] As an ordinary Member: you can submit a test request but not edit it
      afterwards, nor anyone else's.
- [ ] As a Change Manager: you can triage it (Impact, Approver, Status).
- [ ] Populate **CH Change Managers**; delete the test row (as a manager).
- [ ] Even as an owner: changing a deployed column's type, choices or
      settings is refused (sealed) and List settings offers no "Delete
      this list"; a display-name rename is still possible — it is
      drift, reverted and reported at the next re-paste.

## Redeploying

Bump `schema_version`, rebuild, re-paste. The submit-only level's
permissions and the five declared views are reconciled every run; views you
create yourself are user content and are never touched.

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
