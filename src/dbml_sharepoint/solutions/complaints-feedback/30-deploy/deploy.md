# Deploying complaints & feedback (administrator)

Shared procedure: [`templates/README.md`](../../README.md) with
`<name> = complaints-feedback`. Run order: **assess** the target site
(paste `build/assess.js.txt`, read-only; the verdict must be COMPATIBLE or an
accepted DEGRADED) → **review** `build/deploy-manifest.md` (must show 0
validation errors) → **paste** `build/deploy.js.txt` from a Site Owner's
console → **verify** against the checklist below. Template-specific notes
follow.

## Before you build

- [ ] `CF_` prefix free on the target site.
- [ ] Enums match your obligations (regulated sectors: your scheme may
      prescribe outcome categories — align now). **`Status` and `Outcome`
      members are named inside deployed view filters, form visibility
      rules and the list save rule.** Renaming `Closed`, `Received` or
      `Responded` changes what the form shows and what it refuses, not
      just the words in a dropdown; the build will refuse a stale name in
      a formatter map, but a view filter naming a member that no longer
      exists simply returns nothing. Decide the vocabulary **before first
      deploy**.
- [ ] The **SLA table in `50-govern/governance.md` is written down**
      before you paste. The two day-count bars are drawn against a fixed
      scale — 10 days for acknowledgement, 30 for closure — chosen from
      that table's defaults. If your statutory timeframes differ, change
      the two `max:` values in `mapping.yaml` at the same time, or the
      bars will be reassuring about a breach.
- [ ] You know who forms **CF Feedback Recorders** (front line) and
      **CF Feedback Handlers** — this template grants ordinary site Members
      nothing at all, so unlisted staff see nothing.
- [ ] The header shows `Feedback: <title>` on a saved item and `New
      feedback` before the title is typed, updating live.

## Optional: the seeded demonstration build

The response clocks, the severity ladder and four of the five views are
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
first, then `demo-data.js.txt`, from the same bundle. It creates six items —
one per status and one per severity band, an unacknowledged complaint so
*Triage* and *Unacknowledged* both fill, and two closed items inside the
rolling thirty-day report window, one of them a compliment. Every title is
neutral and carries no names, which is also what the staff guide asks of
real ones.

**Delete the demo rows before active use.** Every demo Title begins with
`[DEMO] `, so they are obvious in every view, they are matched by Title on
re-paste (running it twice never duplicates), and `rollback.js.txt` treats a
list whose rows are *all* demo-marked as demo-only content. Do not seed a
site that already holds real feedback.

## After the paste — verification checklist

- [ ] `CF_Feedback` exists; custom level **CF Record Only** exists.
- [ ] All five declared views appear: **Open by handler** (the default),
      **Triage**, **Unacknowledged**, **Closed last 30 days**, **The
      learning shelf**. If you seeded, none is empty. The generated **All
      Items** recovery view is hidden from the modern view bar because
      this template has an authored default.
- [ ] **What replaced "Monthly report".** The old recommended-views table
      asked for items *closed in month*, grouped by type, with both
      day-counts and the outcome. Two things about the shipped
      replacement:
      - It is a **rolling thirty days**, not a calendar month, and the
        title says so. CAML — the language SharePoint view filters are
        written in — has no calendar-month predicate; `today-30` is what
        exists. On the first business day of a month the two answers
        differ, and someone reconciling a committee pack will notice.
      - It **averages both clocks** per feedback type. Each collapsed
        type shows a mean Days To Acknowledge and a mean Days To Close,
        with an overall figure for the window — the acknowledgement mean
        especially, since it is the measure most organisations fail
        first. Means rather than sums: adding day-counts across
        complaints answers nothing. A **calendar**-month mean still needs
        an export, because the window is rolling.
- [ ] Access split verified with three accounts:
      - ordinary Member: **cannot see the list at all**;
      - Recorder: can submit, cannot edit after saving;
      - Handler: can triage and edit.
- [ ] Received `2026-07-01`, Acknowledged `2026-07-03`, Closed `2026-07-15`
      → **Days To Acknowledge = 2**, **Days To Close = 14**. Both draw as
      bars, and both take their **colour from Severity** rather than from
      their own value — two days is green on a Standard item and red on a
      Critical one, which is the point.
- [ ] The New form shows five sections — **What was raised**, **Triage**,
      **Response**, **Ownership**, **System** — each holding the fields
      named in `20-configure/formatting/feedback-form-body.json`.
      **System** holds only the two calculated day-counts, so on the New
      form it renders as a bare heading. That is cosmetic and expected.
- [ ] The New form asks a **recorder** only what a recorder can answer:
      **Handler**, **Acknowledged Date**, **Outcome**, **Closed Date** and
      **Learning** are all absent from it. On an existing item, set
      `Status` to **Responded** and **Outcome** appears; set it to
      **Closed** and **Closed Date** and **Learning** appear too. Move it
      back to **Investigating** and all three hide again, keeping whatever
      was entered.
- [ ] Save rules. Each of the three dates refuses a future value with its
      own message. The list carries **two** chained rules sharing one
      message, because SharePoint gives a list a single validation
      formula: move `Status` off **Received** with **Acknowledged Date**
      empty, and set `Status` to **Closed** with **Outcome** or **Closed
      Date** empty. Both are refused; both show the same message naming
      both checks. Note that the field named in each refusal is on screen
      when it fires — that is what the visibility rules above exist for.
- [ ] Two things this register wants that are **not** enforced at save,
      and cannot be — `50-govern/governance.md` says what carries them
      instead:
      - `Learning` at closure. It is a rich-text column and SharePoint
        validation formulas cannot reference rich text at all.
      - The acknowledgement **timeframe**. Days To Acknowledge is a
        calculated column, and validation formulas cannot read those
        either. The SLA is a review, not a refusal.
- [ ] List Settings → Indexed columns shows `Status`, `FeedbackType`,
      `Severity` and `ReceivedDate`.
- [ ] Populate both working groups; delete the test row (as Handler).
- [ ] Even as an owner: changing a deployed column's type, choices or
      settings is refused (sealed) and List settings offers no "Delete
      this list"; a display-name rename is still possible — it is
      drift, reverted and reported at the next re-paste.

## Redeploying

Bump `schema_version`, rebuild, re-paste. The Record Only level's
permissions are reconciled every run.

## Enterprise reporting access

The deploy declares the `Enterprise Readers` site group — shared with every
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
