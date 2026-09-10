# Deploying the deployment log (administrator)

Shared procedure: [`templates/README.md`](../../README.md) with
`<name> = deployment-log`. Run order: **assess** the target site (paste
`build/assess.js.txt`, read-only; the verdict must be COMPATIBLE or an accepted
DEGRADED) -> **review** `build/deploy-manifest.md` (must show 0 validation
errors) -> **paste** `build/deploy.js.txt` from a Site Owner's console ->
**verify** against the checklist below. Template-specific notes follow.

This family is different from the rest of the collection in one way, and it
is worth reading before you build: its lists are the addresses every other
family's deploy writes to. Deploying this family is the *only* way the
central log gets created. No other deploy creates it, by design, and none of
them creates the site either.

## Before you build

- [ ] **The logging site exists.** Create it by hand: SharePoint start page
      -> Create site -> Team site, named so it is obviously infrastructure
      rather than somebody's workspace. This tool provisions lists, never
      sites, so a missing site is an error you fix once rather than
      something a deploy invents for you.
- [ ] The site is one you are content to leave in place. Every deploy in
      the fleet writes to it, so moving it later means re-pointing every
      project that stamps it.
- [ ] `prefix` names your organisation, and every firmfooting application
      writing to this log needs to agree on it. Shipped as `firmfooting_`,
      giving list titles `firmfooting_Deployments` and `firmfooting_Changes`,
      which is what other families' deploys probe for by default. Changing
      it moves the target; if you do, set `DBMLSP_DEPLOY_LOG_LIST` and
      `DBMLSP_DEPLOY_CHANGES` to the new titles in every project that stamps
      this log, and `DBMLSP_DEPLOY_LOG_SITE` to the site title.
- [ ] The `StampKind` members are a contract, not a preference: the deploy
      scripts write the literal strings `deployment start`, `deployment stop`,
      `abort` and `provenance` to `Deployments`. Renaming one makes every
      stamp of that kind fail its choice-field validation. Decide **before
      first deploy** whether you are keeping them, and keep them.
- [ ] Members of this site will hold **submit-only** on both lists: add a
      row, read back only the rows they wrote, edit and delete nothing. That
      is what an operator deploying another family somewhere else needs in
      order to stamp, and no more. Check who is in the site's Members group
      before you paste, and read "The drop box" below for what they can and
      cannot do afterwards.

## Optional: the seeded demonstration build

An empty deployment log demonstrates nothing, and this one starts empty on a
site nobody has deployed from yet. To see the five views, the `StampKind`
pills and both forms working, rebuild with `--seed`:

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
first, then `demo-data.js.txt`, from the same bundle. It creates six rows
across two source sites: a complete run (start, provenance, stop) on
`Deployments`, one change row from it on `Changes`, and a run that aborted,
so every declared view on both lists has content and every `StampKind`
member renders in its own colour.

**Delete the demo rows before the log carries real stamps.** Every demo Title
begins with `[DEMO]`, so they are obvious in every view, they are matched by
Title on re-paste (running it twice never duplicates), and `rollback.js.txt`
requires per-list confirmation before every delete.

## After the paste: verification checklist

- [ ] `firmfooting_Deployments` and `firmfooting_Changes` both exist, spelled
      exactly that way (or with your chosen prefix, if you changed it).
      Anything else and the fleet's stamps will not find them.
- [ ] `Deployments` shows its four declared views: **Latest first** (the
      default), **Aborted runs**, **Runs**, **Provenance**. `Changes` shows
      its one declared view, **Latest first** (also the default there). If
      you seeded, none of them is empty. The generated **All Items** recovery
      view is hidden from the modern view bar on both lists because each has
      an authored default.
- [ ] On `Deployments`, List Settings -> Indexed columns shows `StampKind`,
      `SourceSite`, `StampUtc` and `Application`. On `Changes`, it shows
      `SourceSite`, `ChangeKey`, `IsCurrent` and `Application`. The build
      manifest lists the same, per list. `Changes` is the one in the
      catalogue that grows with every change any firmfooting application
      makes anywhere in the tenant: a deploy closing a change row filters
      `SourceSite and ChangeKey and Application and IsCurrent` as one
      four-way AND.
      [Microsoft documents](https://learn.microsoft.com/troubleshoot/sharepoint/lists-and-libraries/fails-filtering-sharepoint-column)
      that such a filter is blocked once it would scan past the list view
      threshold without an indexed column, and recommends leading with the
      most selective one, not that every side of an AND needs its own; all
      four columns are indexed here as a precaution.
- [ ] The New form on `Deployments` shows four sections: **The stamp**,
      **Where it ran**, **What was deployed**, **What the run did**, each
      holding the fields named in
      `20-configure/formatting/deployment-log-form-body.json`. The New form
      on `Changes` shows four sections of its own: **The change**, **Where it
      happened**, **Before and after**, **When**, named in
      `20-configure/formatting/changes-form-body.json`. Nothing is hidden on
      either: a person annotating a log by hand should see every field a
      script would have filled.
- [ ] Save rule, on both lists: a **Stamp UTC** dated tomorrow is refused,
      and the message names UTC. Any time up to the moment you save is
      allowed. The rule compares against the instant of the save rather than
      against midnight, so a row written a minute ago is accepted.
- [ ] Two rules these lists want are **not** enforced at save, by
      construction: "a stop stamp needs a start stamp for the same site" and
      "exactly one current row per key, site and application" both read more
      than the row being saved, and no SharePoint validation formula reads
      another row. They stay reporting queries; `50-govern/governance.md`
      says who runs them.
- [ ] The `StampKind` pills render on `Deployments`: `abort` red,
      `deployment stop` green, `deployment start` grey, `provenance` muted.
- [ ] Inheritance is broken on both lists, and List Settings -> Permissions
      for each shows exactly four entries: Site Members on
      **firmfooting Deployments Submit Only**, `dbml List
      Administrators` on Full Control, Site Owners on Full Control, and
      `dbml Enterprise Readers` on Full Control. The Edit that Members
      inherit from the site must **not** be among them on either list; if it
      is, the reconcile did not run and that list is not a drop box.
- [ ] Advanced settings shows, on both lists, **Read access: Read items that
      were created by the user** and **Create and Edit access: Create items
      and edit items that were created by the user**.
- [ ] Neither list holds a row for its own first deploy, and that is correct
      rather than a fault. The logging phase probes for the central lists
      before any list is provisioned, so on the run that creates them the
      probe finds nothing and skips. Every deploy after this one stamps,
      including the next re-paste of this family.
- [ ] Even as an owner: changing a deployed column's type, choices or
      settings is refused (sealed) on either list, and List settings offers
      no "Delete this list"; a display-name rename is still possible. It is
      drift, reverted and reported at the next re-paste.

## The drop box

These lists are written by people who are not administrators of them, from
sites that are not this one, and the record of what a deploy did is only
worth keeping if the person it describes cannot rewrite it. So both lists are
a drop box, in three parts that only work together.

**The level.** `firmfooting Deployments Submit Only` carries
eight permissions: AddListItems, ViewListItems, ViewVersions, ViewFormPages,
Open, ViewPages, BrowseUserInfo, UseRemoteAPIs. It does **not** carry
EditListItems or DeleteListItems, and those two absences are the posture. A
Member can add a row and cannot change or remove one afterwards, including
one they wrote a second ago. One level, shared by both `Deployments` and
`Changes`.

**The item scope.** ReadSecurity 2 and WriteSecurity 2 on each list: a Member
reads back only the rows they created. The level already withholds Edit, so
WriteSecurity is the belt to that braces, and it is what stops a future
binding that does carry Edit from reaching other people's rows by accident.

**The reconcile.** Members inherit Edit from the site. `reconcile: exact`
makes the declared assignments an allowlist and removes every other direct
binding on a list, so the inherited Edit is replaced rather than added to.
Inheritance is broken with `copyRoleAssignments=false`, so it is never
copied down in the first place; the reconcile is the second of the two.

What a Member can do: add a row, see their own rows, see the views and the
form. What a Member cannot do: read anybody else's rows, edit any row,
delete any row, or change the list.

**The assumption about you.** Whoever deploys *this* family to the logging
site is an owner or an administrator of it, so they keep Full Control
through Site Owners and are unaffected by everything above. Operators
deploying *other* families to *other* sites are ordinary Members here, and
submit-only is exactly the right of theirs their deploy uses. If your
deploying account is neither, add it to `dbml List Administrators` before
you rely on the log.

**One consequence, and it is visible in the data.** A central change row is a
type-2 record: writing a new one normally closes the previous current row for
the same site, key and application by setting `EffectiveTo` and
`IsCurrent: false`, on `Changes`. Closing a row is an edit, and submit-only
holds no EditListItems, so an operator writing from another site appends the
new row and leaves the old one open. The deploy probes for the edit bit and
says so in one INFO line when it cannot close. Read currency as **the latest
`EffectiveFrom` per `SourceSite`, `ChangeKey` and `Application`** rather than
trusting `IsCurrent`, unless the writing account holds Full Control here.

### TODO: probe the reader posture before trusting anything narrower

`dbml Enterprise Readers` is granted **Full Control** on both lists. That is
a decision, not a default, and it is more than reading needs: it carries
DeleteListItems and ManagePermissions on the two lists this whole posture
exists to protect. It is shipped on the argument that a deployment log's
integrity matters and its confidentiality does not, and because a reporting
account that exists to read the whole fleet is useless if ReadSecurity 2
trims it to its own rows.

Measured on 2026-09-05 against this posture as shipped on the single
combined list this family has since split: the created-by trim
does **not** spare a narrower level that merely looks read-shaped. An account
holding site membership (no special level at all) saw none of another
account's rows, could add a row, and was refused editing it (403), deleting
it (403) and editing any row it could not see (404: the trim hides the row,
the write path refuses it). A read-shaped grant below Full Control would
still be trimmed unless it carries more bits than a "reader" name implies,
which is exactly the trap. Until a candidate level is probed the same way
(write rows as account A, read as account B, record what B sees), treat the
Full Control elevation as deliberate. The build already warns about it, with
the finding code `enterprise_reader_on_trimmed_list`.

## Then point the fleet at it

The stamps are on by default and address these lists by their defaults, so a
project deploying to the site titled `firmfooting-logging` with the lists
titled `firmfooting_Deployments` and `firmfooting_Changes` needs no
configuration at all. If any title differs, put the relevant ones in that
project's `dbml-sharepoint.env`:

```text
DBMLSP_DEPLOY_LOG_SITE=your-logging-site
DBMLSP_DEPLOY_LOG_LIST=firmfooting_Deployments
DBMLSP_DEPLOY_CHANGES=firmfooting_Changes
```

Setting any of them to empty disables the corresponding writes for that
project: the site or the deployments list disables the whole pair, and the
change list alone disables only the change feed, leaving the stamps
untouched.

**The two lists are probed and written independently, straight after each
other.** Only the Deployments probe decides whether a project's run is
CENTRAL at all; the Changes probe never promotes or demotes it. A `Changes`
list that is absent, unreachable, redeployed with a different title, or
missing a declared column costs that project's change feed alone -- its
stamps still land on `Deployments` in full.

Prove it end to end before you rely on it: deploy any other family to any
other site, and watch `Deployments`' **Latest first** view gain a
`deployment start` row, a `provenance` row and a `deployment stop` row, and
`Changes`' **Latest first** view gain a row for anything that deploy
altered. If nothing arrives on one list but the other fills as expected,
read that deploy's transcript: each list is probed and named separately,
and three INFO lines per list say which of the three probes failed -- the
site was not found, the list was not found, or the operator cannot add
items to it. A failed probe **skips** that list's writes; it never fails the
deploy, which is why a silent absence has to be checked for rather than
waited for.

A deploy that reaches `Deployments` writes its stamps here and creates no
per-site sidecar lists at all: no `dbml_Deployments`, no `dbml_Changes`. The
mode is chosen once, before any list is provisioned, from whether
`Deployments` answers its probe, and it never changes mid-run. A deploy that
cannot reach it falls back to the two site-local lists, which is the old
behaviour and the reason they still exist. So the sidecars appearing on a
source site is the signal that its stamps are not arriving here, and their
absence is the signal that they are.

## Redeploying

Bump `schema_version`, rebuild, re-paste. Re-pasting does not touch the rows
already in the log.

A site that ran an earlier version of this family keeps `dbml-deployment-log`
beside the new `firmfooting_Deployments` and `firmfooting_Changes`: this tool
never renames, deletes or writes to it again. It is safe to delete by hand
once its rows are no longer wanted. `50-govern/governance.md` has the full
disposal note, including the two hidden per-site lists this rename also
retires.

## Enterprise reporting access

The deploy declares the `dbml Enterprise Readers` site group, shared with
every other family deployed to the site, and grants it `Full Control` on
every list in this family, not the plain `Read` other families in the
collection grant it: see the TODO above for why. The group starts empty
only if no family has deployed to the site yet; it gains a member when
any family's build is run with
`--enterprise-reader <account>`, which enrols exactly that one account and
nothing else. `rollback.js.txt` does not remove it: rollback deletes lists,
not site groups or role assignments, so the group and any account enrolled in
it survive a rollback.

A later build that omits the flag does not put the group back to empty:
enrolment only runs when `--enterprise-reader` is given, so an account
enrolled by an earlier build keeps its membership and its `Full Control`
grant. Removing it is manual. Clear it in Site permissions > Groups.

If the group already holds anyone other than that account, the deploy
**aborts before enrolling** and removes nobody. Before you clear anyone out,
check who it is: the group is shared by every family on this site, so the
unexpected member is most likely another family's reporting account, and
removing it silently breaks that family's reporting. Agree one reader account
for the site and rebuild with that address, or rebuild without the flag.

Read access matters more here than on a single register. These lists are the
only place the whole estate's deploy history is visible, so they are the
natural source for a fleet report, and a reporting account that can read
them can answer "which sites are behind" without opening any of them.
