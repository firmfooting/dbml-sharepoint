# Deployment log: governance

## Ownership

| Role | Held by | Accountable for |
| --- | --- | --- |
| Log owner | *(e.g. the person who owns the SharePoint estate)* | The logging site, retention, this document |
| Deploying operators | n/a | Being in this site's Members group before they deploy anywhere |
| Whoever reviews the estate | n/a | The unfinished-run and abort sweeps below |

## What the list enforces at save, and what stays a governance check

The list enforces one thing itself, with its own message on the form:

| Enforced at save | Rule |
| --- | --- |
| `StampUtc` | Cannot be in the future |

Everything else here is a **governance check**: a sweep, a review or a
permissions decision, not something SharePoint refuses. Two of them look
enforceable and are not, and the reason is worth recording so nobody spends
an afternoon trying:

- **A stop stamp with no matching start.** That rule reads a second row, and
  a SharePoint validation formula sees only the row being saved. It cannot be
  expressed at any strength, so it is the unfinished-run sweep below.
- **A stamp claiming a site it did not come from.** Rows arrive cross-web
  from whoever pasted a deploy elsewhere, and `SourceSite` is a text column
  the script fills, not an identity SharePoint checks. Anyone who can add a
  row here can write any site into it. The control is who is in the Members
  group, not a formula. What the permissions do close is the second half of
  it: having written a wrong site, they cannot go back and edit it, and the
  row keeps their name on it.

## The silent-failure this list has, and how to notice it

An operator who cannot add items here gets a **graceful skip**, not an error.
That is deliberate: a permissions problem on a logging site must never fail a
deploy on a production one. The cost is that a site whose stamps stop arriving
looks exactly like a site nobody has deployed to.

So the absence has to be swept for rather than waited for:

1. Once a quarter, list the sites you believe this tool has deployed to, and
   check each appears in **Latest first** within its expected window.
2. A site that is missing entirely is usually a permissions problem, not an
   idle site. The deploy transcript on that site names which of the three
   probes failed.
3. When a site is added to the estate, deploy something to it and confirm the
   stamp arrives, before anyone relies on the log covering it.

## Permissions

This list is a **drop box**, and it is the one family in the collection whose
permissions are a control rather than a convenience. Site Members hold
`dbml Log Submit Only`: they may add a row, read back only the rows they
created, and edit or delete nothing, including what they wrote themselves.
That is exactly what an operator deploying any family anywhere needs and no
more. The mechanism is in `30-deploy/deploy.md` under "The drop box"; the
governance point is that the record of what somebody's deploy did cannot be
rewritten by the person it describes.

Full Control stays with `dbml List Administrators`, which is empty by default
and gains the running operator per deploy of *this* family, with the site
owners, and with `dbml Enterprise Readers`.

Three decisions the log owner makes and records here:

1. **Who is in this site's Members group.** It is the set of people whose
   deploys will be recorded. Anyone outside it deploys silently.
2. **Who is in `dbml List Administrators`.** They are the only accounts that
   can correct or remove a row, and the only ones whose deploys can close a
   superseded change row rather than appending beside it. Keep it small and
   review it when it changes.
3. **Whether the site is open to readers.** The estate's deploy history is
   not sensitive in itself, but it names operators and site URLs, so it is a
   map of what exists and who touches it. Read access: ______.

`dbml Enterprise Readers` holds Full Control here rather than Read, because
a read-trimmed list gives a Read holder only its own rows and a fleet
reporting account has none. That is a deliberate elevation on the one list
this posture protects, the build warns about it
(`enterprise_reader_on_trimmed_list`), and `30-deploy/deploy.md` carries the
live probe that has to run before anything narrower is trusted. If you are
not running fleet reporting, empty the group and the elevation costs nothing.

## Data-quality rules

1. Script-written rows are never edited or deleted. A correction is a new row
   saying what actually happened. For Members that is enforced rather than
   asked for, since their level carries no edit or delete; for the
   administrators who can, versioning is on with a 50-version history, so an
   edit stays visible.
2. Hand-written rows say they are hand-written, in Details, in the first
   sentence.
3. `[DEMO]` rows are deleted before the log carries real stamps. A demo row
   left in place is a fabricated deployment record.
4. The unfinished-run sweep: **Runs**, filtered to a site, should alternate
   start and stop. A start with no stop and no abort is either a run that was
   interrupted or a stamp that failed to arrive, and those want different
   answers.

## Retention

Deployment stamps are **operational records of change**, not personal data in
any meaningful sense, though they do carry operator logins. The default
posture is to keep them: this list is small per deploy, and its value is
entirely in being long-running. "When did this site last change, and to what?"
is a question asked years later.

If you do set a retention period, set it in whole releases rather than in
months, and never delete the provenance rows: they are the only record of
which version of the tool built what. Chosen period: ______.

## Lifecycle

This list is expected to **grow forever** and is the one family in the
collection where that is the design rather than a smell. It grows faster than
the stamps alone suggest, because a deploy that reaches this list writes its
change feed here too and makes no per-site sidecars at all. The indexes on
`StampKind`, `SourceSite`, `StampUtc`, `ChangeKey` and `IsCurrent` are what
keep the filtered views and the change-row close working past the list view
threshold; do not remove them.

Never run `rollback.js.txt` against this list once it holds real stamps.
Rolling it back deletes the estate's entire deployment history, and no other
copy exists. The per-site sidecars are not a backup: a site only has them
for the runs that could not reach this list, and its run log is Title-only.
