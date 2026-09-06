# Deployment log: staff guide

Almost nobody writes in these lists. They fill themselves, from the deploy
scripts run on every other site. This guide is about reading them, and about
the one occasion you add a row by hand.

## What a row means

`Deployments` holds a row written at one moment by one deploy run. Four
kinds:

- **deployment start**: a run began. It says what was about to be deployed,
  where, and by whom, before anything was changed.
- **provenance**: what built the bundle. The release, the schema version and
  the deployer version, which is the row a support question is answered from.
- **deployment stop**: the run finished. Its Details carry the counts: errors,
  lists created, columns added, how long it took.
- **abort**: the run stopped early. Something was refused and the run did not
  complete. Read the Details.

A complete run leaves a start, a provenance and a stop. A start with no stop
and no abort means the browser tab was closed, the network dropped, or the
person walked away; treat it as unfinished until somebody says otherwise.

You may also see a fifth kind, **change**, on `Deployments`: today's writer
still posts a central change row there rather than to `Changes`, so a row
carrying it is the same change-feed content described below, in the wrong
list for now. Read it the same way you would a `Changes` row.

`Changes` holds one row per change a run made: which list, level or group,
the old value, the new value, and the window the value held for. A run
leaves one of these per change and none if it changed nothing. Read it
grouped by site and application, because a change key identifies a thing
within one site and application, and two of either can raise the same key
for different lists.

## Reading it

On `Deployments`, **Latest first** is the default view and answers the usual
question: what has changed recently, anywhere. **Runs** drops the provenance
rows so start and stop sit next to each other and you can read a run's
duration off the list. **Provenance** is the reverse: what version of the
tool built what, per site.

On `Changes`, **Latest first** is the detail under a run: not that a deploy
happened, but what it did.

**Aborted runs**, on `Deployments`, should be short, and every row in it
deserves an answer. An abort is not a failure of this list; it is the deploy
refusing to leave a site half-changed. The question it raises is whether
somebody went back and finished the job.

## When you do write a row

One case: annotating what a run actually did, after the fact. A run aborted
and you fixed the cause by hand; a deploy was run twice on purpose; a site was
rebuilt from scratch. Add a row to `Deployments` saying so, in your own
words, so the next person reading the log does not have to reconstruct it.

1. **New** -> **The stamp**: a Title that reads as a sentence, the closest
   `StampKind`, and **Stamp UTC** set to when it actually happened. The form
   refuses a time in the future and tells you why.
2. **Where it ran**: the site URL, the application (usually `dbml-sharepoint`,
   unless another firmfooting application ran it), and yourself as Operator.
3. **What was deployed**: fill in what you know and leave the rest empty.
   A blank is honest; a guessed version number is not.
4. **What the run did**: this is the part worth writing. What happened, and
   what you did about it.

Leave `Changes` alone. Its rows belong to the type-2 feed a deploy writes,
and a hand-typed one will not line up with the `EffectiveFrom`/`EffectiveTo`
pairing the reader relies on.

## What NOT to do

- Do not edit or delete a stamp or change row a script wrote. It is the
  record of what happened, not a record of what should have happened.
  Correct it by adding a row to `Deployments` that says so. This one is
  enforced rather than asked for: unless you administer these lists,
  SharePoint will refuse, and for the same reason you see your own rows and
  not anybody else's. If you need to read the whole log, ask the log owner
  for access rather than for edit rights.
- Do not use these lists as a change register. They record what this tool
  did to SharePoint, not what your organisation decided. The two are
  different questions and the second one has its own family.
- Do not rename columns, entities or `StampKind` choices, even if a title
  reads oddly. Every deploy in the estate writes to these exact names, and a
  rename stops the stamps arriving with no error anywhere.
