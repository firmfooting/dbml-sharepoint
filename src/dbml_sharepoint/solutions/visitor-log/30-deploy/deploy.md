# Deploying the visitor log (administrator)

Shared procedure: [`templates/README.md`](../../README.md) with
`<name> = visitor-log`. Run order: **assess** the target site (paste
`build/assess.js.txt`, read-only; the verdict must be COMPATIBLE or an accepted
DEGRADED) → **review** `build/deploy-manifest.md` (must show 0 validation
errors) → **paste** `build/deploy.js.txt` from a Site Owner's console →
**verify** against the checklist below. Template-specific notes follow.

## Before you build

- [ ] `VI_` prefix free on the target site.
- [ ] Kiosk decision made: reception records, or a mounted tablet showing
      the New-item form for self-service (both work with nothing extra).
- [ ] The paper book has a cutover date.
- [ ] `VisitorType` matches the classes of person who actually arrive at
      your front door. Two of its members — **Contractor** and **Student /
      placement** — are what make the *Induction sighted* tick appear on
      the form, so renaming or removing them changes the form as well as
      the enum. Decide **before first deploy**.
- [ ] The header shows `Visit: <name>` on a saved row and `New visit`
      before the name is typed, updating live as it is typed.

## Optional: the seeded demonstration build

An empty visitor log demonstrates nothing: *On site now* is the whole
product and it starts blank. To see the views, the type pills and the
"On site" rendering working, rebuild with `--seed`:

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
first, then `demo-data.js.txt`, from the same bundle. It creates six visits —
three people still on site (one of them signed in yesterday, so *Never
signed out* has a row), a contractor with an induction ticked, a student
placement, and completed visits — enough that all four declared views have
content.

**Delete the demo rows before active use.** Every demo Title begins with
`[DEMO] `, so they are obvious in every view, they are matched by Title on
re-paste (running it twice never duplicates), and `rollback.js.txt` treats a
list whose rows are *all* demo-marked as demo-only content. Do not seed a
site that already holds real visits.

## After the paste — verification checklist

- [ ] `VI_Visit` exists and all four declared views appear: **On site now**
      (the default), **Signed in today**, **Contractors on site**, **Never
      signed out**. If you seeded, none of them is empty. The generated
      **All Items** recovery view is hidden from the modern view bar
      because this template has an authored default.
- [ ] **Open *On site now* on a phone, signed in, before you rehearse the
      muster procedure.** It is the default view, so the list opens on it —
      but the warden who will use it at the assembly point should have done
      that once on their own device, in advance, rather than for the first
      time in the rain.
- [ ] Two of the four views are substitutions for what this template's old
      recommended-views table promised, and the difference is worth
      knowing:
      - **Signed in today** filters `SignedInAt ≥ today`, not `= today`.
        CAML's `<Today/>` is midnight, so an equality test on a *datetime*
        column matches only a sign-in stamped at exactly 00:00 — the
        promised view would have been permanently empty.
      - **Never signed out** filters `SignedInAt < today`, which is
        "before midnight this morning" rather than "more than 24 hours
        ago". Someone who signed in at 23:50 last night appears in it at
        00:01, which is what a morning tidy-up wants.
- [ ] List Settings → Indexed columns shows `SignedInAt`, `VisitorType`
      and `VisitLocation`. The build manifest lists the same three.
- [ ] The New form shows three sections — **Who is visiting**, **On site**
      and **Induction** — each holding the fields named in
      `20-configure/formatting/visit-form-body.json`.
- [ ] The form reacts as you fill it in. On a New form, **Signed Out At**
      is absent: nobody signs out at the moment they arrive, and it appears
      on the Edit form. **Induction sighted** is absent until `VisitorType`
      is set to **Contractor** or **Student / placement**, then appears;
      set it back to **Visitor** and it disappears again, keeping whatever
      was ticked.
- [ ] Save rules: a **Signed In At** dated next month is refused with its
      own message, and so is a future **Signed Out At**. Both allow any
      time up to the moment you save — each formula compares against
      `NOW()`, so the refusal bites within the hour rather than at
      midnight. If it refuses a sign-in stamped a few minutes ago, the rule
      has been edited back to a whole-day bound.
- [ ] Two rules this register wants are **not** enforced at save, by
      construction rather than by omission — `50-govern/governance.md` says
      what carries them instead:
      - a sign-out earlier than its own sign-in (a column-to-column
        comparison, which the condition grammar does not express);
      - a visitor with no host (SharePoint validation formulas cannot read
        person columns at all).
- [ ] Sign a test visitor in. *On site now* shows them, and **Signed Out
      At** renders as an "On site" chip rather than an empty cell. Sign
      them out: the cell becomes the time they left and the row leaves the
      view.
- [ ] Any Member can create and edit rows (hosts sign their own guests
      in and out).
- [ ] Front desk bookmark / kiosk form set up.
- [ ] Delete the test row.
- [ ] Even as an owner: changing a deployed column's type, choices or
      settings is refused (sealed) and List settings offers no "Delete
      this list"; a display-name rename is still possible — it is
      drift, reverted and reported at the next re-paste.

## Redeploying

Bump `schema_version`, rebuild, re-paste.

## Enterprise reporting access

The deploy creates an empty `"VI Enterprise Readers"` site group holding `Read` on
every list in this family. It stays empty unless the build was run with
`--enterprise-reader <account>`, which enrols exactly that one account
and nothing else. `rollback.js.txt` does not remove it: rollback deletes
lists, not site groups or role assignments, so the group and any account
enrolled in it survive a rollback.
