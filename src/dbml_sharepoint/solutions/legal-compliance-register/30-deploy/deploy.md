# Deploying legal compliance register (administrator)

Shared procedure: [`templates/README.md`](../../README.md) with
`<name> = legal-compliance-register`. Run order: **assess** the target site
(paste `build/assess.js.txt`, read-only; the verdict must be COMPATIBLE or an
accepted DEGRADED) -> **review** `build/deploy-manifest.md` (must show 0
validation errors and name the folder phase) -> **paste** `build/deploy.js.txt`
from a Site Owner's console -> **verify** against the checklist below.
Template-specific notes follow.

## Before you build

- [ ] `LC_` prefix free on the target site.
- [ ] The `division` enum in `10-design/schema.dbml` and
      `entities.SAQ.folders` in `20-configure/mapping.yaml` match, name for
      name. Folders are never renamed after go-live, because the URL is the
      file's identity, so settle the names now.
- [ ] The `committee` enum matches the committees that receive compliance
      reporting.
- [ ] The named licence holders are known. `Topic.LicenceHolder` is
      required on every topic.
- [ ] The site owner has agreed the site's sharing setting (owners only).
      Sharing a file breaks inheritance on that file, and under
      `reconcile: exact` the next deploy stops on the stranded item scope
      for review rather than erasing it.
- [ ] You know who forms **LC Compliance Coordinators** and
      **LC Assessment Owners**.
- [ ] Anybody who syncs the library through the OneDrive client knows it
      syncs read-only: Microsoft documents that a library with validation
      columns or metadata is synchronised read-only (Microsoft Learn,
      "SharePoint files open as read-only"), and this library carries both,
      so files are opened from the library in the browser rather than from
      a synced folder.
- [ ] The header on a SAQ shows the file name, and `New SAQ` before one is
      chosen. The header on a topic shows `Topic: <title>`, and `New topic`
      before the title is typed, updating live.

## Optional: the seeded demonstration build

The status colours, the overdue dates, the folder-spanning views and the
loop-closing view are all invisible on an empty library. To see them
working, rebuild with `--seed`:

```bash
dbml-sharepoint build \
  --schema 10-design/schema.dbml \
  --mapping 20-configure/mapping.yaml \
  --release 20-configure/release.yaml \
  --site-url https://yourtenant.sharepoint.com/sites/your-site \
  --time-zone Region/City \
  --site-role default \
  --seed \
  --out ./build
```

That bundle contains an extra file, `demo-data.js.txt`. Paste `deploy.js.txt`
first, then `demo-data.js.txt`, from the same bundle. It creates six topic
rows (five Active across the four divisions, one Retired) and uploads six
demo files, at least one into every folder, with the panel filled: one
file per assessment status except *No longer required*, every compliance
result, one overdue, one confirmed but not yet recorded, and one recorded.

**Delete the demo files and rows before loading real topics.** Every demo
file name and every demo Title begins with `[DEMO]`, so they are obvious in
every view. Files are matched by name within their folder on re-paste and
rows by Title, so running it twice never duplicates. `rollback.js.txt`
requires per-list confirmation before every delete, and a deleted file goes
to the recycle bin.

## After the paste: verification checklist

- [ ] `LC_Topic` exists. `LC_SAQ` exists as a document library with the
      four folders at its root and nothing else there.
- [ ] Three Topic views: **Active topics** (the default), **By business
      owner**, **Retired**. Five SAQ views: **Pending** (the default),
      **My responsibility**, **My accountability**, **Overdue**,
      **To record in the portal**. If you seeded, none is empty, and
      **To record in the portal** empties once you set a recording date on
      the Food safety demo file. The generated **All Items** recovery view
      is hidden from the modern view bar on both, because both have an
      authored default.
- [ ] Every SAQ view shows files from every folder (recursive scope), and
      **Pending** groups by Division, not by folder. Open a folder and the
      library's own folder-scoped listing shows that folder's files only;
      switch to **Pending** and every folder's files return.
- [ ] The file panel header shows the file name, not a blank Title.
- [ ] Library settings -> Indexed columns shows `Topic`, `Status`,
      `DueDate`, `Division`, `PeriodYear`, `Quarter`, `BusinessOwner` and
      `ExecutiveResponsible`. List settings on the register shows
      `Division`, `BusinessOwner`, `ExecutiveResponsible` and `Status`,
      plus the unique index on `ExternalRef` and the automatic one on
      `Title` as the lookup's display column. The build manifest lists the
      same.
- [ ] The New form on the register shows **The topic**, **Who owns it** and
      **Reporting and standing**. The file panel on the library shows
      **The SAQ**, **Complete it**, **Confirm it** and **Record in the
      portal**, each holding the fields named in the body JSON under
      `20-configure/formatting/`. Neither has a System section: nothing on
      either is auto-stamped.
- [ ] The panel reacts as you fill it in. **Completed date** and
      **Recorded in portal** are absent until Status is *Complete*;
      **Action link** is absent until Compliance is *Partially compliant*
      or *Non-compliant*. A field that hides again keeps its value;
      SharePoint has no mechanism to clear it.
- [ ] The library carries **one** save rule with one message, three checks
      chained, because SharePoint gives a list a single validation formula.
      Try each: set *Submitted* with Compliance at *Not assessed*; set
      *Complete* with **Completed date** empty; set *In progress* with
      **Division** or **Due date** empty. All three are refused, all three
      show the same message naming all three checks. Two hoisted date rules
      join it: a future **Completed date** or **Recorded in portal** date is
      refused, and their sentences join the list message.
- [ ] **Period year** refuses a two-digit year with its own message, because
      it reads only its own column and so keeps a message of its own.
- [ ] Upload any file into a division folder: the panel opens with **Period
      year** and **Quarter** already filled with the current year and
      calendar quarter. On the first day of a quarter the pre-fill can name
      the previous one until the afternoon, because the formula engine's
      clock runs behind the site (see the mapping reference, "Which clock
      today reads"). Correct both for a SAQ filed after its quarter ended.
- [ ] `DueDate` escalates to the severe treatment once it is past, and stops
      once the status is *Complete* or *No longer required*.
- [ ] **LC Contribute No Delete** exists under Site permissions ->
      Permission levels, and **LC Assessment Owners** holds it on the
      library and `Read` on the register.
- [ ] As a member of **LC Assessment Owners**: can edit a file's panel and
      upload a new version, cannot delete a file, cannot edit a topic. As an
      ordinary site Member: read-only on both.
- [ ] Manual library settings the paste does not make, and a redeploy does
      not check. Each is its own box because nothing else will notice it
      missing:
  - [ ] Activate the **Document ID** site collection feature (Site
        settings -> Site collection features).
  - [ ] Apply the default **retention label** to the library (Library
        settings -> Apply label). The class is a records-governance
        decision, not this family's.
  - [ ] Library settings -> **Column default value settings**: set
        `Division` per folder to the folder's own name.
  - [ ] Library settings -> Advanced settings: hide the **New Folder**
        command, so every file lands in a division folder.
  - [ ] Leave **Open documents in** at the server default (browser).
- [ ] **Load the topic register first**, from the portal's profile export
      (a spreadsheet of a profile's topics), then file the current period's
      SAQs into their folders and fill the panel at upload.
- [ ] Populate **LC Compliance Coordinators** and **LC Assessment Owners**;
      delete the demo files and rows.
- [ ] Even as an owner: changing a deployed column's type, choices or
      settings is refused (sealed) and neither settings page offers "Delete
      this list"; a display-name rename is still possible. It is drift,
      reverted and reported at the next re-paste.

## What is not enforced at save

Three rules stay governance checks because a SharePoint validation formula
cannot read the column. The topic and the two owner columns on a SAQ are a
lookup and two person columns, which cannot be operands. The action link
on a gap result is a hyperlink column, which SharePoint refuses in a
validation formula outright (measured; see the mapping reference). A
required column would not have closed the first gap either: a file
uploaded over REST lands with a required column empty and is not checked
out. **Pending** shows both owners beside every open file and **My
accountability** shows **Action link** beside **Compliance**, so an
absence is visible where the row is reviewed. See
`50-govern/governance.md`.

## Redeploying

Bump `schema_version`, rebuild, re-paste. Existing rows and files are
untouched; drifted settings are reconciled, and declared views are
reconciled to the declaration: a view retitled by hand comes back under its
declared title. Declared folders are verified and created if missing; the
files inside them are never touched, a folder that is not declared is left
alone, and a file found where a folder was declared stops the run. The
five manual settings above are not checked by any redeploy.

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
it is manual: clear it in Site permissions > Groups.

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
