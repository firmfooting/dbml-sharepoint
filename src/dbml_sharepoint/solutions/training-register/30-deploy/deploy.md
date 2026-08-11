# Deploying the training register (administrator)

Shared procedure: [`templates/README.md`](../../README.md) with
`<name> = training-register`. Run order: **assess** the target site (paste
`build/assess.js.txt`, read-only) → **review** `build/deploy-manifest.md` (must
show 0 validation errors) → **paste** `build/deploy.js.txt` from a Site Owner's
console → **verify** against the checklist below. Template-specific notes
follow.

## Before you build

- [ ] `TR_` prefix free on the target site.
- [ ] `Category` enum matches your training framework.
- [ ] You know who forms **TR Training Coordinators**.
- [ ] Decide your sweep window. The template ships **60 days**, in the
      `Expiring 60 days` view's `today+60`. Widen it if your refreshers
      take longer to book than they do to run — the number is in
      `20-configure/mapping.yaml`, once, and the view title says it so
      nobody has to guess which window they are looking at.
- [ ] Each header shows `Course: <name>` / `Training record: <title>` on a
      saved row and `New course` / `New training record` before the title
      is typed, updating live.

## Optional: the seeded demonstration build

The status colours, the sweep window and the two grouped views are all
invisible on an empty list. To see them working, rebuild with `--seed`:

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
first, then `demo-data.js.txt`, from the same bundle. It creates five courses
and six records: a lapse and its refresher recorded as two rows, one
record inside the sweep window, one already flagged Expiring, and two
courses that never expire.

Two things the demo deliberately does not do:

- **Evidence URLs are left blank.** A SharePoint URL column takes a
  structured value over REST rather than a bare string, and this
  repository does not seed a write it has not read back from a live list.
  Link one by hand on any demo row to see the column work.
- **Every record belongs to the person who pasted it.** Demo person
  columns resolve to the operator, so the *By person* view demonstrates as
  one group. That is the mechanism, not a defect — the grouping is real,
  there is simply one person in the sample.

**Delete the demo rows before active use.** Every demo Title begins with
`[DEMO] `, they are matched by Title on re-paste (running it twice never
duplicates), and `rollback.js.txt` treats a list whose rows are *all*
demo-marked as demo-only content. Do not seed a site that already holds
real records.

## After the paste — verification checklist

- [ ] `TR_Course` and `TR_TrainingRecord` exist, catalogue created first.
- [ ] All three **Course** views appear: **Catalogue** (the default,
      grouped by Category), **Mandatory catalogue**, **Never expires**.
- [ ] All four **TrainingRecord** views appear: **By person** (the
      default, grouped by Person and collapsed), **Expiring 60 days**,
      **By course** (grouped by the Course lookup, collapsed),
      **Expired**. If you seeded, none of the seven is empty. The
      generated **All Items** recovery view is hidden from the modern view
      bar on both lists, because each has an authored default.
- [ ] **Seed the catalogue** — enter your required courses/certifications
      with their `ValidityMonths` before any records; the record form's
      Course dropdown reads from it.
- [ ] The Course form shows **The course**, **Requirement and validity**
      and **Booking and content**. The record form shows **Who and what**,
      **When**, **Evidence** and **Currency and notes**. Every column sits
      in one of them.
- [ ] **Status is absent from the New record form** and present on Edit
      and Display. It defaults to *Current*, which is what a new
      completion is; the weekly sweep is what changes it, and a required
      field pre-filled correctly on the New form only invites someone to
      change it to something the sweep has not decided yet.
- [ ] An expiry date in the past renders with the severe treatment and a
      warning icon. Set that record's Status to **Expired** and the date
      goes plain — the chip carries the signal from there, and two of them
      shouting is how people learn to stop reading the colour.
- [ ] Save rules, all three:
      - A course with **Validity Months** of `0` or a negative number is
        refused; leaving it **blank** saves, and means "never expires".
      - A record with a **Completed Date** in the future is refused.
      - A record set to **Expiring** or **Expired** with no **Expiry
        Date** is refused, with the list's message.
- [ ] As an ordinary Member: both lists read-only.
- [ ] Populate **TR Training Coordinators**; delete the test record.
- [ ] Even as an owner: changing a deployed column's type, choices or
      settings is refused (sealed) and List settings offers no "Delete
      this list"; a display-name rename is still possible — it is
      drift, reverted and reported at the next re-paste.

### What is not enforced at save

The governance rule that a Current record must link its evidence is **not**
a save rule, and that is a decision rather than an omission. Two reasons,
the second of which is the real one: the build has no verified evidence
that a URL column can be an operand in a SharePoint validation formula,
and *linked* is not *sighted* in any case. A rule that passes on a link to
the wrong document buys nothing and costs the coordinator a save. It stays
a quarterly spot-check — see `50-govern/governance.md`.

## Note on expiry status

`Status` is **not** self-updating — SharePoint calculated columns cannot
reference "today", so the template deliberately leaves status maintenance to
the coordinators' weekly sweep (see `50-govern/governance.md`) or to a small
scheduled automation you add later. The `ExpiryDate` index keeps either
approach a single cheap filtered query.

## Redeploying

Bump `schema_version`, rebuild, re-paste. Rows untouched; views, forms,
formatting and save rules reconciled to the declaration.

## Enterprise reporting access

The deploy creates an empty `"TR Enterprise Readers"` site group holding `Read` on
every list in this family. It stays empty unless the build was run with
`--enterprise-reader <account>`, which enrols exactly that one account
and nothing else. `rollback.js.txt` does not remove it: rollback deletes
lists, not site groups or role assignments, so the group and any account
enrolled in it survive a rollback.
