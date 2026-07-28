# Deploying tiered huddle boards (administrator)

Shared procedure: [`templates/README.md`](../../README.md) with
`<name> = tiered-huddle`. Template-specific notes below.

## Before you build

- [ ] `TH_` prefix free on the target site.
- [ ] The reporting streams in `10-design/schema.dbml` are yours, not the
      shipped placeholders. Renaming a stream after deploy is a manual
      SharePoint operation; renaming it now is a text edit.
- [ ] First deploy? Delete the shipped retirement example — the
      `EnvironmentStatus` / `EnvironmentNote` pair in `Tier3Board` and the
      `retired_columns:` block in `mapping.yaml`. It is there to show the
      mechanism, and there is no history to preserve on a site that has
      never held this list.
- [ ] Running two tiers rather than three? Delete the unused board list from
      `schema.dbml` (including its `indexes` block), from `mapping.yaml`
      (`entities`, `versioning.overrides`, `display_names.overrides`,
      `field_sets`, `views`, `column_formatting`, `form_formatting`,
      `form_visibility`, `list_validation`, `demo_items`) **and** delete
      its form body from `20-configure/formatting/`.
- [ ] The huddle chairs are site Members. The security model gives Members
      and Owners Contribute; nobody needs a bespoke group.

## After the paste — verification checklist

- [ ] `TH_Tier1Board`, `TH_Tier2Board`, `TH_Tier3Board` and `TH_Escalation`
      exist.
- [ ] Each board opens on **Last 14 days** and shows the status columns
      without the note columns.
- [ ] Create a board row for today, then try to create a second row with the
      same date — SharePoint refuses it. `BoardDate` is unique; that is the
      one-row-per-day guarantee.
- [ ] On a new board row, **Stood down reason** is not shown while
      **Huddle held** is *Held*, and appears the moment you change it. It is
      a conditional-visibility formula on the column, not a form layout
      trick.
- [ ] Set `HuddleHeld` to *Stood down* and save with `StoodDownReason`
      empty. Expected refusal: **"A huddle that was stood down or cancelled
      needs a reason."**
- [ ] On the new-item form, the fields are grouped **Header / Streams /
      Wrap-up**, not one flat scroll.
- [ ] Set a stream status to Red and check the grid renders it as
      SharePoint's severe box with an icon. Clear it again and check the cell
      goes blank and grey — that grey cell is the unreported signal.
- [ ] If you kept the retirement example: `Environment Status (retired)` and
      `Environment Note (retired)` are absent from every view and from the
      **new**-item form, and present on an existing item. That asymmetry is
      the whole point — retirement stops collection without hiding history.
- [ ] On `TH_Escalation`, set Status to *Resolved* and save with `Resolution`
      empty. Expected refusal: **"Resolving or closing an escalation needs a
      resolution and a resolved date."**
- [ ] `Route` fills itself in as `Tier 2 -> Tier 3` and does not appear on
      the new or edit form (calculated columns never do). A calculated
      column over two Choice columns is undocumented by Microsoft but was
      probed against a live tenant and works
      (`test/manual/calculated-choice-operand.js`). If your tenant refuses
      it anyway, delete `Route` from `schema.dbml`, delete its
      `calculated_formulas` entry, and group the **By route** view on
      `TargetTier` instead.
- [ ] The **By route** view groups the queue on `Route`, collapsed.
- [ ] Any ordinary Member can create rows on all four lists (Contribute).
- [ ] Delete the test rows.
- [ ] Even as an owner: changing a deployed column's type, choices or
      settings is refused (sealed) and List settings offers no "Delete this
      list"; a display-name rename is still possible — it is drift, reverted
      and reported at the next re-paste.

## Optional: the seeded demonstration build

The heat grid is invisible on an empty list. To show the template working,
rebuild with `--seed`:

```bash
dbml-sharepoint build \
  --schema templates/tiered-huddle/10-design/schema.dbml \
  --mapping templates/tiered-huddle/20-configure/mapping.yaml \
  --release templates/tiered-huddle/20-configure/release.yaml \
  --site-url https://yourtenant.sharepoint.com/sites/your-site \
  --site-role default \
  --seed \
  --out ./build
```

That bundle contains an extra file, `demo-data.js`. Paste `deploy.js` first,
then `demo-data.js`, from the same bundle. It creates a fortnight of Tier 3
board rows ending today and six escalations — enough that every declared view
has content.

**Delete the demo rows before active use.** Every demo Title begins with
`[DEMO] `, so they are obvious in every view, they are matched by Title on
re-paste (running it twice never duplicates), and `rollback.js` treats a list
whose rows are *all* marked as demo-only content. Do not seed a site that
already holds real records.

## The stream lifecycle

Streams change: functions merge, move between tiers, or stop reporting. Both
operations are ordinary redeploys — the deployer unseals for its own run and
re-seals afterwards.

### Adding a stream

Worked example — adding **Wellbeing** to the Tier 1 board.

1. `10-design/schema.dbml`, in `Table Tier1Board`, beside the other stream
   pairs:

   ```dbml
   WellbeingStatus rag_status [note: 'Leave blank if wellbeing did not report; blank is a visible gap, not a pass']
   WellbeingNote   longtext   [note: 'Needed when the status is not Green: what changed, and what you are doing about it']
   ```

2. `20-configure/mapping.yaml`, in `field_sets.Tier1Board`: add
   `WellbeingStatus` to `statuses` and `WellbeingNote` to `notes`. Every view
   that references those sets picks the columns up — you do not touch
   `views:` at all.

3. Same file, in `column_formatting.Tier1Board`:

   ```yaml
   WellbeingStatus: { style: severity, map: { Green: good, Amber: warning, Red: severe, "Not applicable": muted } }
   ```

4. `20-configure/formatting/tier1-form-body.json`: add `"WellbeingStatus"`
   and `"WellbeingNote"` to the **Streams** section `fields` array. Internal
   names, and mind the JSON commas.

5. Bump `schema_version` in `20-configure/release.yaml`, rebuild, re-paste
   `deploy.js`.

Four files, in the same order every time: the schema declares it, the field
sets project it into every view, `column_formatting` colours it,
`formatting/tierN-form-body.json` places it on the form.

Existing rows get the new columns blank. That is correct: the stream was
genuinely unreported on those days, and the grid says so.

### Retiring a stream

Worked example — Tier 3 folds **Environment** into **Facilities**. This one
is shipped, so you can read the result in `mapping.yaml` rather than imagine
it:

```yaml
retired_columns:
  Tier3Board:
    EnvironmentStatus:
      retired: "2026-07-01"
      superseded_by: FacilitiesStatus
      reason: "Environment folded into Facilities at the July board review"
    EnvironmentNote:
      retired: "2026-07-01"
      superseded_by: FacilitiesNote
      reason: "Environment folded into Facilities at the July board review"
```

Bump `schema_version`, rebuild, re-paste. What that one block does:

- the columns leave every declared view;
- they leave the **New** form, so nobody is asked to fill them in again;
- they stay on the edit and display forms, so the history is readable and
  correctable — the modern display form follows the edit form, and the two
  cannot be separated, so "readable but not editable" is not a state
  SharePoint has. Add `hide_existing: true` if you want them gone from
  those forms as well;
- their display titles gain `" (retired)"`;
- every value ever recorded stays in the list and in the reporting bundle.

You do not touch `field_sets` — a retired column named in a set is stripped
rather than rejected, though the build tells you it did so. Removing the
names yourself keeps the declaration honest, and this template does.

Leave the `column_formatting` entry in place: historical values then still
render in colour wherever the column is still shown.

The form body in `20-configure/formatting/tier3-form-body.json` is the other
place worth a hand tidy. A retired name left in a **Streams** section is
stripped by the build, with a warning naming it — harmless, but the warning
is telling you the file no longer describes the form.

### Do NOT delete the retired columns from `schema.dbml`

This is the trap, and it is worth stating plainly. Deleting the declaration
does not delete anything on the site. It leaves a live, visible, deletable
column that the schema no longer declares — and the generated
`_UserAddedColumns.pq` drift audit then reports it as a user-added column on
**every refresh, forever**. That audit is only worth running because any row
in it means "investigate". One wrongly deleted declaration is enough to
destroy that contract.

Leave the declaration. `retired_columns` is the mechanism; the DBML stays.

The one exception is a template you have never deployed: nothing exists on
the site yet, so nothing can be stranded. That is why the checklist above
tells a first-time deployer to delete the shipped Environment pair outright.

## Redeploying

Bump `schema_version`, rebuild, re-paste. Adding or retiring a stream is a
schema change and always warrants the bump.
