# Deploying the onboarding tracker (administrator)

Shared procedure: [`templates/README.md`](../../README.md) with
`<name> = onboarding-tracker`. Run order: **assess** the target site (paste
`build/assess.js`, read-only) → **review** `build/deploy-manifest.md` (must
show 0 validation errors) → **paste** `build/deploy.js` from a Site Owner's
console → **verify** against the checklist below. Template-specific notes
follow.

## Before you build

- [ ] `OB_` prefix free on the target site.
- [ ] `TaskFunction` enum matches the teams that actually onboard people.
      It drives the grouping of the default task view, so a function
      missing from the enum is a function with no queue.
- [ ] **Privacy check**: the site's membership is scoped to onboarding
      participants (starter records are personal data — see governance).
- [ ] The standard task set in `50-govern/GOVERNANCE.md` has been reviewed
      by each function.
- [ ] Each header shows `Starter: <name>` / `Task: <title>` on a saved row
      and `New starter` / `New onboarding task` before the title is typed,
      updating live.

## Optional: the seeded demonstration build

The grouped queues, the overdue colouring and the conditional Done Date
are all invisible on empty lists. To see them working, rebuild with
`--seed`:

```bash
dbml-sharepoint build \
  --schema templates/onboarding-tracker/10-design/schema.dbml \
  --mapping templates/onboarding-tracker/20-configure/mapping.yaml \
  --release templates/onboarding-tracker/20-configure/release.yaml \
  --site-url https://yourtenant.sharepoint.com/sites/your-site \
  --site-role default \
  --seed \
  --out ./build
```

That bundle contains an extra file, `demo-data.js`. Paste `deploy.js`
first, then `demo-data.js`, from the same bundle. It creates four starters
covering every status and six tasks — including one that nobody has picked
up and which is already past due with the start date still ahead, which is
the row *Overdue before start* exists to find.

The starters describe a **role**, not a person: this tracker holds
personal data, and seeding it with invented names would teach the wrong
reflex on the first screen anyone sees. Every person column resolves to
the operator, so *My tasks* demonstrates as your own queue.

**Delete the demo rows before active use.** Every demo Title begins with
`[DEMO] `, they are matched by Title on re-paste (running it twice never
duplicates), and `rollback.js` treats a list whose rows are *all*
demo-marked as demo-only content.

## After the paste — verification checklist

- [ ] `OB_Starter` and `OB_OnboardingTask` exist (Starter first).
- [ ] All three **Starter** views appear: **In progress** (the default),
      **Starting soon**, **Complete and withdrawn**.
- [ ] All four **OnboardingTask** views appear: **Open by function** (the
      default, grouped by Task Function and collapsed), **My tasks**,
      **By starter** (grouped by the Starter lookup, collapsed),
      **Overdue before start**. If you seeded, none of the seven is empty.
      The generated **All Items** recovery view is hidden from the modern
      view bar on both lists, because each has an authored default.
- [ ] **My tasks** shows *your* open tasks and changes per signed-in user.
      Ask a colleague to open the same view and confirm they see theirs,
      not yours — that is the whole test.
- [ ] Create a test starter; create tasks against them — the Starter lookup
      offers the test row; TaskFunction/DueDate are required.
- [ ] The Starter form shows **The hire**, **Start and ownership** and
      **Progress**. The task form shows **The task**, **Who and when** and
      **Outcome**. Every column sits in one of them.
- [ ] **Done Date** is absent from a new task and from any open one. Set
      Status to **Done** and it appears. Set Status back to **Open** and it
      hides again, **keeping whatever was typed** — SharePoint has no
      mechanism to clear it.
- [ ] An open task past its due date renders with the severe treatment and
      a warning icon. Close it Done and the date goes plain; the chip
      carries it from there.
- [ ] Save rules, all three:
      - A **Done Date** in the future is refused, with its own message.
      - Status **Done** with no Done Date is refused.
      - Status **Not applicable** with empty Notes is refused. Both of
        those last two show the same message naming both checks — a list
        has a single validation formula, so every cross-column rule shares
        one message. That is the platform limit, not a defect.
- [ ] Any site Member can create and update rows.
- [ ] Delete the test tasks then the test starter.
- [ ] Even as an owner: changing a deployed column's type, choices or
      settings is refused (sealed) and List settings offers no "Delete
      this list"; a display-name rename is still possible — it is
      drift, reverted and reported at the next re-paste.

### Two views this template used to recommend, and what ships instead

- **"My function's queue"** — the old table specified `TaskFunction =
  (theirs)`, which is not buildable. The current-user sentinel resolves to
  the signed-in **user** and is permitted on person columns only;
  `TaskFunction` is a Choice, and SharePoint has no notion of which choice
  member the reader belongs to, so there is nothing for the filter to
  compare. What ships is **Open by function**: one view, grouped by Task
  Function and collapsed, so each function opens its own group. One view
  rather than six, and it stays correct when the enum changes.

  The per-**person** queue that row was reaching for does ship, as **My
  tasks** — `AssignedTo` is a person column, which is exactly the case the
  sentinel exists for. It is also why `40-adopt/STAFF-GUIDE.md` tells
  people to put themselves in AssignedTo when they pick a task up.

- **"Per starter"** — a static view cannot filter to one parent record.
  The choices were N views that rot as hires are added, or one grouped
  view that does not. What ships is **By starter**, grouped by the Starter
  lookup and collapsed, unfiltered so a manager reading their own hire
  sees the Done and Not applicable rows too — "everything is closed" is
  the answer they are checking for.

## Redeploying

Bump `schema_version`, rebuild, re-paste. Rows untouched; views, forms,
formatting and save rules reconciled to the declaration.
