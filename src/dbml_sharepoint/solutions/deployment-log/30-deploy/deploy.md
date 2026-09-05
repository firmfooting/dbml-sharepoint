# Deploying the deployment log (administrator)

Shared procedure: [`templates/README.md`](../../README.md) with
`<name> = deployment-log`. Run order: **assess** the target site (paste
`build/assess.js.txt`, read-only; the verdict must be COMPATIBLE or an accepted
DEGRADED) -> **review** `build/deploy-manifest.md` (must show 0 validation
errors) -> **paste** `build/deploy.js.txt` from a Site Owner's console ->
**verify** against the checklist below. Template-specific notes follow.

This family is different from the rest of the collection in one way, and it
is worth reading before you build: its list is the address every other
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
- [ ] `prefix` is empty and stays empty. The list title `dbml-deployment-log`
      is what other families probe for; a prefix renames the target and the
      stamps stop arriving. If you must rename it, set `DBMLSP_DEPLOY_LOG_LIST`
      to the new title in every project that stamps this log, and
      `DBMLSP_DEPLOY_LOG_SITE` to the site title.
- [ ] The `StampKind` members are a contract, not a preference: the deploy
      scripts write the literal strings `deployment start`, `deployment stop`,
      `abort` and `provenance`. Renaming one makes every stamp of that kind
      fail its choice-field validation. Decide **before first deploy** whether
      you are keeping them, and keep them.
- [ ] Members of this site will hold **Contribute** on the list. That is what
      an operator deploying another family somewhere else needs in order to
      stamp. Check who is in the site's Members group before you paste.

## Optional: the seeded demonstration build

An empty deployment log demonstrates nothing, and this one starts empty on a
site nobody has deployed from yet. To see the four views, the `StampKind`
pills and the form working, rebuild with `--seed`:

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
first, then `demo-data.js.txt`, from the same bundle. It creates five stamps
across two source sites: a complete run (start, provenance, stop), and a run
that aborted, so all four declared views have content and every `StampKind`
member renders in its own colour.

**Delete the demo rows before the log carries real stamps.** Every demo Title
begins with `[DEMO]`, so they are obvious in every view, they are matched by
Title on re-paste (running it twice never duplicates), and `rollback.js.txt`
requires per-list confirmation before every delete.

## After the paste: verification checklist

- [ ] `dbml-deployment-log` exists, spelled exactly that way, with no prefix
      in front of it. Anything else and the fleet's stamps will not find it.
- [ ] All four declared views appear: **Latest first** (the default),
      **Aborted runs**, **Runs**, **Provenance**. If you seeded, none of them
      is empty. The generated **All Items** recovery view is hidden from the
      modern view bar because this template has an authored default.
- [ ] List Settings -> Indexed columns shows `StampKind`, `SourceSite` and
      `StampUtc`. The build manifest lists the same three. This list is the
      one in the catalogue that grows with every deploy anywhere in the
      tenant, so the indexes are what keep the filtered views working past
      the list view threshold.
- [ ] The New form shows four sections: **The stamp**, **Where it ran**,
      **What was deployed** and **What the run did**, each holding the fields
      named in `20-configure/formatting/deployment-log-form-body.json`.
      Nothing is hidden: a person annotating the log by hand should see every
      field a script would have filled.
- [ ] Save rule: a **Stamp UTC** dated tomorrow is refused, and the message
      names UTC. Any time up to the moment you save is allowed. The rule
      compares against the instant of the save rather than against midnight,
      so a stamp written a minute ago is accepted.
- [ ] One rule this list wants is **not** enforced at save, by construction:
      "a stop stamp needs a start stamp for the same site" reads two rows, and
      no SharePoint validation formula reads another row. It stays a reporting
      query; `50-govern/governance.md` says who runs it.
- [ ] The `StampKind` pills render: `abort` red, `deployment stop` green,
      `deployment start` grey, `provenance` muted.
- [ ] Site Members hold **Contribute** on the list, `dbml List Administrators`
      holds Full Control, and inheritance is broken.
- [ ] The log holds no row for its own first deploy, and that is correct
      rather than a fault. The logging phase probes for the central list
      before any list is provisioned, so on the run that creates it the probe
      finds nothing and skips. Every deploy after this one stamps, including
      the next re-paste of this family.
- [ ] Even as an owner: changing a deployed column's type, choices or
      settings is refused (sealed) and List settings offers no "Delete this
      list"; a display-name rename is still possible. It is drift, reverted
      and reported at the next re-paste.

## Then point the fleet at it

The stamps are on by default and address this list by its defaults, so a
project deploying to the site titled `firmfooting-logging` with the list
titled `dbml-deployment-log` needs no configuration at all. If either title
differs, put both in that project's `dbml-sharepoint.env`:

```text
DBMLSP_DEPLOY_LOG_SITE=your-logging-site
DBMLSP_DEPLOY_LOG_LIST=dbml-deployment-log
```

Setting either to empty disables the stamps for that project.

Prove it end to end before you rely on it: deploy any other family to any
other site, and watch **Latest first** gain a `deployment start` row, a
`provenance` row and a `deployment stop` row for that site. If nothing
arrives, read that deploy's transcript. Three INFO lines say which of the
three probes failed: the site was not found, the list was not found, or the
operator cannot add items to it. A failed probe **skips** the stamp; it never
fails the deploy, which is why a silent absence has to be checked for rather
than waited for.

## Redeploying

Bump `schema_version`, rebuild, re-paste. Re-pasting does not touch the rows
already in the log.

## Enterprise reporting access

The deploy declares the `dbml Enterprise Readers` site group, shared with
every other family deployed to the site, and grants it `Read` on every list in
this family. The group starts empty only if no family has deployed to the site
yet; it gains a member when any family's build is run with
`--enterprise-reader <account>`, which enrols exactly that one account and
nothing else. `rollback.js.txt` does not remove it: rollback deletes lists,
not site groups or role assignments, so the group and any account enrolled in
it survive a rollback.

A later build that omits the flag does not put the group back to empty:
enrolment only runs when `--enterprise-reader` is given, so an account
enrolled by an earlier build keeps its membership and its `Read` grant.
Removing it is manual. Clear it in Site permissions > Groups.

If the group already holds anyone other than that account, the deploy
**aborts before enrolling** and removes nobody. Before you clear anyone out,
check who it is: the group is shared by every family on this site, so the
unexpected member is most likely another family's reporting account, and
removing it silently breaks that family's reporting. Agree one reader account
for the site and rebuild with that address, or rebuild without the flag.

Read access matters more here than on a single register. This list is the
only place the whole estate's deploy history is visible, so it is the natural
source for a fleet report, and a reporting account that can read it can
answer "which sites are behind" without opening any of them.
