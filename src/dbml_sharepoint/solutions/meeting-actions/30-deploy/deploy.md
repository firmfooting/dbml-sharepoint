# Deploying meeting actions (administrator)

Shared procedure: [`templates/README.md`](../../README.md) with
`<name> = meeting-actions`. Run order: **assess** the target site (paste
`build/assess.js.txt`, read-only) -> **review** `build/deploy-manifest.md` (must
show 0 validation errors) -> **paste** `build/deploy.js.txt` from a Site Owner's
console -> **verify** against the checklist below. Template-specific notes
follow.

## Before you build

- [ ] `MA_` prefix free on the target site.
- [ ] `MeetingType` choices match your forums. It drives the grouping of
      the *By forum* view, so a forum missing from the enum has no group.
- [ ] Each header shows `Meeting: <title>` / `Decision: <title>` /
      `Action: <title>` on a saved row, and `New meeting` / `New decision`
      / `New action` before the title is typed, updating live.

## Optional: the seeded demonstration build

The grouped queues, the overdue colouring and the conditional Completed
Date are invisible on empty lists, and this template is the one people
judge in the first two minutes. To see it working, rebuild with `--seed`:

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

That bundle contains an extra file, `demo-data.js.txt`. Paste `deploy.js.txt`
first, then `demo-data.js.txt`, from the same bundle. It creates four meetings
across four forums (one deliberately older than the rolling ninety days),
three decisions stated as decisions, and six actions spanning every
status, including one overdue and still open, which is the row the whole
follow-up discipline is about.

**Every demo meeting has a blank Minutes URL.** A SharePoint URL column
takes a structured value over REST rather than a bare string, and this
repository does not seed a write it has not read back from a live list.
Paste one onto a demo meeting by hand to see the column work.

**Delete the demo rows before active use.** Every demo Title begins with
`[DEMO]`, they are matched by Title on re-paste (running it twice never
duplicates), and `rollback.js.txt` requires
per-list confirmation before every delete.

## After the paste: verification checklist

- [ ] `MA_Meeting`, `MA_Decision`, `MA_ActionItem` exist (Meeting first).
- [ ] **Meeting**: **Recent** (the default) and **By forum** (grouped and
      collapsed).
- [ ] **Decision**: **Decision log** (the default) and **By meeting**
      (grouped and collapsed).
- [ ] **ActionItem**: **Open by person** (the default, grouped by Assigned
      To and collapsed), **My actions**, **Overdue**, **By meeting**
      (grouped and collapsed), **Done and dropped**. If you seeded, none
      of the nine is empty. The generated **All Items** recovery view is
      hidden from the modern view bar on all three lists, because each has
      an authored default.
- [ ] **My actions** shows *your* open actions and changes per signed-in
      user. Ask a colleague to open it and confirm they see theirs, not
      yours. That is the whole test.
- [ ] The Meeting form shows **The meeting** and **The record**. The
      Decision form shows **The decision** and **Why**. The action form
      shows **The action**, **Owner and date** and **Progress**. Every
      column sits in one of them.
- [ ] **Completed Date** is absent from a new action and from any open
      one. Set Status to **Done** and it appears. Set Status back to
      **Open** and it hides again, **keeping whatever was typed**.
      SharePoint has no mechanism to clear it.
- [ ] An open or in-progress action past its due date renders with the
      severe treatment and a warning icon. Close it Done or Dropped and
      the date goes plain.
- [ ] Save rules, both of them:
      - A **Completed Date** in the future is refused, with its own
        message.
      - Status **Done** with no Completed Date is refused, with the list's
        message.
      **Dropped** is deliberately not covered by either, see below.
- [ ] Create a test meeting; then a decision and an action against it:
      both Meeting lookups offer the test row.
- [ ] The action demands `AssignedTo` and `DueDate` (required).
- [ ] Any ordinary Member can create all three (Contribute).
- [ ] Delete the test rows (action/decision first, then the meeting).
- [ ] Even as an owner: changing a deployed column's type, choices or
      settings is refused (sealed) and List settings offers no "Delete
      this list"; a display-name rename is still possible. It is
      drift, reverted and reported at the next re-paste.

### Three rows from the old table, and what ships instead

- **"This meeting: filter by Meeting, link it from the agenda"**. A
  static view cannot filter to one parent record; the choices were one
  view per meeting, rotting from the day it was made, or one grouped view
  that never does. What ships is **By meeting**, grouped by the Meeting
  lookup and collapsed. Open the previous meeting's group as your first
  agenda item, the same two minutes, and it keeps working as meetings
  accumulate. It is deliberately **unfiltered**: "did anyone do them?"
  needs the Done and Dropped rows in the answer.

- **"Decision log: sorted newest first"**. Decision carries no date of
  its own; the date belongs to the meeting, on the other list, and CAML
  cannot sort across a lookup. The log sorts by **Created**, and shows it,
  so nobody has to guess what "newest" means. That is the honest proxy
  rather than a new column: decisions are entered during or straight after
  the meeting, so creation order *is* meeting order in practice, and a
  `DecisionDate` column would ask the minute-taker to retype something the
  lookup already knows.

- **A "Recent" meetings view is a rolling ninety days, not "this
  quarter".** CAML has no calendar predicate: `today+/-N` is what exists,
  and the two differ on the first day of a quarter, which is exactly when
  someone assembling a committee pack notices. The view is titled
  *Recent* rather than named for a period, so it cannot lie about which.

### Why "Dropped" carries no save rule

`50-govern/governance.md` asks for a note when an action is dropped, and
`40-adopt/staff-guide.md` says the same. Neither is enforced, on purpose.
Dropping an action is already the honest move against leaving it Open
forever, and a template whose first act is to make the honest move harder
than the dishonest one has its incentives backwards. **Done** is
different: a Done with no date is a claim, so it is refused.

## Redeploying

Bump `schema_version`, rebuild, re-paste. Rows untouched; views, forms,
formatting and save rules reconciled to the declaration.

## Enterprise reporting access

The deploy declares the `dbml Enterprise Readers` site group, shared with every
other family deployed to the site, and grants it `Read` on every list in this
family. The group starts empty only if no family has deployed to the site yet;
it gains a member when any family's build is run with `--enterprise-reader
<account>`, which enrols exactly that one account and nothing else.
`rollback.js.txt` does not remove it: rollback deletes lists, not site groups
or role assignments, so the group and any account enrolled in it survive a
rollback.

A later build that omits the flag does not put the group back to empty:
enrolment only runs when `--enterprise-reader` is given, so an account enrolled
by an earlier build, of this family or any other sharing the site, keeps its
membership and its `Read` grant on every list it was declared against. Removing
it is manual. Clear it in Site permissions > Groups.

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
`Use Remote Interfaces` intact at web scope. Publishing sites, where
lockdown mode is on by default, and the reporting client's own list
enumeration are still unverified, so the end-to-end path (Power BI or any
other API client) is not yet proven. See the danger block in the mapping
reference's Security section.
