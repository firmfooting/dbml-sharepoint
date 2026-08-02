# Deploying routine checks (administrator)

Shared procedure: [`templates/README.md`](../../README.md) with
`<name> = routine-checks`. Run order: **assess** the target site (paste
`build/assess.js.txt`, read-only; the verdict must be COMPATIBLE or an accepted
DEGRADED) → **review** `build/deploy-manifest.md` (must show 0 validation
errors) → **paste** `build/deploy.js.txt` from a Site Owner's console →
**verify** against the checklist below. Template-specific notes follow.

## Before you build

- [ ] `RC_` prefix free on the target site.
- [ ] The paper checklists being replaced are collected — each becomes a
      CheckPoint row, and the paper stops the day this goes live (parallel
      running means neither record is complete).
- [ ] Out-of-range escalations per check type agreed in
      `50-govern/GOVERNANCE.md` and mirrored into each checkpoint's
      Instructions.
- [ ] **`Result` members are named in a deployed view filter, a form rule
      and the list save rule.** `Out of range - action taken` and `Out of
      range - escalated` are the two that trigger the mandatory Action
      taken; `In range - OK` is what the *Out of range* view excludes; and
      `Unable to check` is deliberately left out of the save rule, because
      an honest gap must stay cheap to record. Renaming any of them
      changes behaviour, not just wording. Decide **before first deploy**.
- [ ] The Check header shows `Check: <title>` on a titled entry and just
      `Check` on an untitled one — **not** "New check". Title is optional
      there, because an entry is identified by its checkpoint and its
      time.

## Optional: the seeded demonstration build

Six views over two empty lists demonstrate nothing, and the one thing this
register exists for — an out-of-range reading, in colour, with the action
beside it — is the thing an empty list cannot show. Rebuild with `--seed`:

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
first, then `demo-data.js.txt`, from the same bundle. It creates four
checkpoints — a vaccine fridge, a resus trolley, a security round and one
retired — and six entries, one per Result, including an escalated
cold-chain breach with its action recorded. Show that row to whoever is
sponsoring the deployment; it is the whole business case in one line.

**Delete the demo rows before active use.** Every demo Title begins with
`[DEMO] `, so they are obvious in every view, they are matched by Title on
re-paste (running it twice never duplicates), and `rollback.js.txt` treats a
list whose rows are *all* demo-marked as demo-only content. Do not seed a
site that already holds real check history.

## After the paste — verification checklist

- [ ] `RC_CheckPoint` and `RC_CheckEntry` exist (CheckPoint first).
- [ ] `RC_CheckPoint` has **The catalogue** (the default, grouped by check
      type) and **Retired checkpoints**. `RC_CheckEntry` has **Today** (the
      default), **Out of range**, **Escalated** and **By checkpoint**. If
      you seeded, none is empty. The generated **All Items** recovery view
      is hidden from the modern view bar on both lists.
- [ ] **What replaced the old recommended-views table**, since two of its
      four rows could not be built as written:
      - **"Per checkpoint"** — described as "the history an auditor
        reads" — asked for a view filtered to one checkpoint. SharePoint
        has no per-parent filter, so building it meant hard-coding one
        fridge into a filter that rots the next time the catalogue
        changes, or one view per checkpoint. It ships as **By checkpoint**:
        one view grouped on the CheckPoint lookup, collapsed. The auditor
        expands the checkpoint they want and reads the same history, and a
        new checkpoint appears in it with no work.
      - **"Today"** specified `CheckedAt = today`. That filter returns
        nothing on a datetime column: CAML's `<Today/>` is midnight, so an
        equality test matches only a check stamped at exactly 00:00. It
        ships filtering `CheckedAt ≥ today`, which is the same day's
        checks.
      - A fourth view, **Escalated**, was added. Governance's weekly review
        asks whether escalated entries reached their escalation point, and
        that question had no surface.
- [ ] **Load the checkpoint catalogue** — every fridge, trolley, round
      and route, with range, frequency, owner and instructions.
- [ ] The catalogue refuses an **active** checkpoint with no **Acceptable
      Range**, with its own message. Every entry's Result is a judgement
      against those words, so a checkpoint without them cannot be checked,
      only guessed at. (Frequency and Owner are required by the schema
      already. **Instructions is rich text and cannot be required by a
      formula** — SharePoint validation cannot reference rich-text columns
      at all — so it stays a governance check.)
- [ ] Record a test entry: the CheckPoint lookup offers the catalogue;
      CheckedAt takes date **and time**; Reading and Result are required.
      Set Result to **In range - OK** and there is no **Action taken**
      box. Set it to either out-of-range value, or to **Unable to check**,
      and the box appears.
- [ ] The list refuses an out-of-range entry with **Action taken** empty,
      with its own message. **Unable to check** is deliberately *not*
      covered: an honest gap is a legitimate answer, and demanding a remedy
      for it is how you teach people to guess a reading instead.
- [ ] A future **Checked At** is refused. The message names the
      retrospective-entry rule, which is the discipline the whole register
      rests on.
- [ ] The CheckEntry New form shows four sections — **The check**, **What
      you found**, **What you did**, **Ownership**. The CheckPoint form
      shows three — **The checkpoint**, **What good looks like**,
      **Ownership**.
- [ ] Colours: an in-range result is green, an out-of-range one the
      checker fixed is amber, and an **escalated** one is the strongest
      treatment in the palette. That last distinction is deliberate — an
      escalated check has left the hands of the person who did it, which
      is a different fact from a fault fixed on the spot.
- [ ] Any Member can record entries.
- [ ] Bookmark/QR the entry form at each physical checkpoint (a QR to the
      list's New form taped where the paper sheet was is the adoption
      trick that makes this stick).
- [ ] Delete the test entry.
- [ ] Even as an owner: changing a deployed column's type, choices or
      settings is refused (sealed) and List settings offers no "Delete
      this list"; a display-name rename is still possible — it is
      drift, reverted and reported at the next re-paste.

## Redeploying

Bump `schema_version`, rebuild, re-paste.
