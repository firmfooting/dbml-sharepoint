# Deploying the grants register (administrator)

Shared procedure: [`templates/README.md`](../../README.md) with
`<name> = grants-register`. Run order: **assess** the target site (paste
`build/assess.js.txt`, read-only; the verdict must be COMPATIBLE or an accepted
DEGRADED) → **review** `build/deploy-manifest.md` (must show 0 validation
errors) → **paste** `build/deploy.js.txt` from a Site Owner's console →
**verify** against the checklist below. Template-specific notes follow.

## Before you build

- [ ] `GR_` prefix free on the target site.
- [ ] `submission_outcome` and `acquittal_status` match your funders'
      language (`10-design/schema.dbml`). Both are colour-mapped in
      `mapping.yaml`, so a renamed member strands old rows *and* silently
      loses its colour.
- [ ] **Decide your obligation horizon before first deploy.** The *Due 90
      days* view filters `DueDate ≤ today+90`. Change the `today+90` in
      `mapping.yaml` now if your sweep runs on a different rhythm — a view
      title and a filter that disagree is worse than either.
- [ ] You know who forms **GR Grants Coordinators**.
- [ ] The headers show `Submission: <title>` and `Obligation: <title>` on
      saved rows, and `New submission` / `New obligation` before the title
      is filled in, updating live as they are typed.

## Optional: the seeded demonstration build

The outcome colours, the overdue row wash and every declared view are
invisible on two empty lists. To see them working, rebuild with `--seed`:

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
first, then `demo-data.js.txt`, from the same bundle. It creates six
submissions — one per outcome, two of them under one funder so *By funder*
has a group with history in it, and two successful grants so *By grant* on
the obligations list has more than one group — and five obligations, one
per acquittal status, including the overdue one that drives the row wash.

**Delete the demo rows before loading your real grants.** Every demo Title
begins with `[DEMO] `, so they are obvious in every view, they are matched
by Title on re-paste (running it twice never duplicates), and `rollback.js.txt`
treats a list whose rows are *all* demo-marked as demo-only content.

## After the paste — verification checklist

- [ ] `GR_Submission` and `GR_Acquittal` exist (Submission first).
- [ ] **Submission** shows four declared views: **Pipeline** (the
      default), **Live grants**, **By funder**, **Lost bids**.
      **Acquittal** shows five: **Open obligations** (the default),
      **Due 90 days**, **Overdue**, **By grant**, **Filed**. If you
      seeded, none of them is empty. The generated **All Items** recovery
      views are hidden from the modern view bar because both lists have an
      authored default.
- [ ] **Open obligations** is the acquittal default, not *Due 90 days*.
      An overdue obligation is outside a ninety-day forward window by
      definition, and a default view that hides the worst rows on the list
      is the opposite of what a default is for. *Due 90 days* is still
      there, and is still THE sweep view.
- [ ] **Due 90 days** is a **rolling** ninety days from whatever day you
      look at it, not "next quarter". CAML has no calendar-period
      predicate, so a period-boundary reading has to come from your own
      reporting.
- [ ] **By grant** is grouped and collapsed on the Submission lookup. A
      static SharePoint view cannot filter to one parent record, so "the
      obligations of *this* grant" is one grouped view rather than one view
      per grant — the real idiom, and it stays correct as grants are added.
- [ ] An **Overdue** row in *Open obligations* carries a tinted row
      background. That is this list's single row-level signal, reserved for
      its worst state; nothing else on either list competes with it.
- [ ] Create a test submission; add an obligation against it (the
      Submission lookup offers it; DueDate required).
- [ ] List Settings → Indexed columns shows `Outcome`, `Funder` and
      `DueDate` on Submission, and `Submission`, `AcqStatus` and `DueDate`
      on Acquittal. The build manifest lists the same six.
- [ ] The Submission New form shows **The bid**, **Submission and
      outcome** and **Delivery**; the Acquittal New form shows **The
      obligation**, **Preparing and filing** and **Escalation notes**. Both
      match the JSON in `20-configure/formatting/`.
- [ ] Both forms react as you fill them in. On a new submission at *In
      preparation*, **Submitted date**, **Amount awarded**, **Agreement
      URL** and **Project end date** are all absent; move to *Submitted*
      and the date appears; move to *Successful* and the other three
      appear. On a new obligation at *Upcoming*, **Submitted date** and
      **Evidence URL** are absent; move to *Submitted* and both appear.
      Moving back hides them again while keeping whatever was typed —
      SharePoint has no mechanism to clear a hidden field.
- [ ] `GR_Submission` carries **two** chained save rules sharing one
      message, because SharePoint gives a list a single validation formula.
      Try each: set *Submitted* with **Submitted date** empty; set
      *Successful* with **Amount awarded** empty. Both are refused, and
      both show the same message naming both checks.
- [ ] `GR_Acquittal` carries **one**: set *Submitted* with **Submitted
      date** empty and the save is refused.
- [ ] Four per-column save rules, each with its own message: a negative
      **Amount sought**, a negative **Amount awarded**, and a future
      **Submitted date** on either list. Each says why. These live on their
      columns rather than on the list because a column rule keeps its own
      message; a list has only one to share.
- [ ] Ordinary Members: read-only.
- [ ] **Load the live estate**: every current grant as a Successful
      submission, then — agreement in hand — every reporting/acquittal
      obligation it contains, with real due dates. This load is the
      whole point; expect it to surface at least one obligation nobody
      was tracking.
- [ ] Populate **GR Grants Coordinators**; delete the test rows.
- [ ] Even as an owner: changing a deployed column's type, choices or
      settings is refused (sealed) and List settings offers no "Delete
      this list"; a display-name rename is still possible — it is
      drift, reverted and reported at the next re-paste.

## What is not enforced at save

Three of `50-govern/governance.md`'s data-quality rules are only half
enforceable, and the missing halves are all the same shape.

- **The linked agreement on a successful bid** (`AgreementUrl`) and **the
  filed copy on a submitted obligation** (`EvidenceUrl`) are hyperlink
  columns. This tool would accept a rule against one; it has never been
  read back from a live tenant inside a SharePoint validation formula, and
  this repository does not ship a rule it has not seen work. Both stay
  governance checks — and the *Live grants* and *Filed* views each show
  the link column, so an empty one is visible where it matters.
- **The debrief on a lost bid** lives in `ProjectSummary`, which is rich
  text, and a validation formula cannot reference a multi-line column at
  all. The *Lost bids* view shows `ProjectSummary` for exactly that
  reason.
- **Loading the obligations within a week of signing** is a rule about a
  habit, not about a row. Nothing on `GR_Submission` can know how many
  `GR_Acquittal` rows point at it.

## Redeploying

Bump `schema_version`, rebuild, re-paste. Existing rows are untouched;
drifted settings are reconciled, and declared views are reconciled to the
declaration — a view retitled by hand comes back under its declared title.

## Enterprise reporting access

The deploy creates an empty `"GR Enterprise Readers"` site group holding `Read` on
every list in this family. It stays empty unless the build was run with
`--enterprise-reader <account>`, which enrols exactly that one account
and nothing else. `rollback.js.txt` does not remove it: rollback deletes
lists, not site groups or role assignments, so the group and any account
enrolled in it survive a rollback.
