# Deploying the digital innovation log

Shared procedure: [`templates/README.md`](../../README.md), with
`<name> = digital-innovation-log`. Assess the target, review the generated
manifest, deploy, apply the manual list settings, then verify with separate
accounts. Do not add champions to their group until the checklist below
passes.

## Before building

- [ ] Replace `service_area` in `10-design/schema.dbml` with the local
      directorates or facilities. Keep the *Not sure* member: a champion who
      guesses an area misroutes the ask, and a steward can route *Not sure*.
- [ ] Trim `m365_workload` to the workloads the service actually licenses.
      A pattern cannot be marked *Available now* on a workload nobody can
      open.
- [ ] Confirm nothing patient-identifiable enters either list. The Problem
      Statement describes a process, never a person; see
      [`sectors/healthcare.md`](../../sectors/healthcare.md).
- [ ] Name the digital team owner of the log and the champions who will
      capture asks. Both go into `DI Champions` and `DI Digital Team` only
      after verification.
- [ ] Replace `https://REPLACE-WITH-CAPTURE-GUIDE-URL` in
      `20-configure/formatting/opportunity-form-header.json` with the
      published capture guide (`40-adopt/staff-guide.md`, or wherever the
      service hosts it).
- [ ] Confirm `DI_` is free on the target site.

## Build

```bash
dbml-sharepoint build \
  --schema 10-design/schema.dbml \
  --mapping 20-configure/mapping.yaml \
  --release 20-configure/release.yaml \
  --site-url https://yourtenant.sharepoint.com/sites/your-site \
  --time-zone Region/City \
  --site-role default \
  --out ./build
```

Review `build/deploy-manifest.md` and continue only with zero errors. Run
`assess.js.txt` first, then `deploy.js.txt`, from a Site Owner's browser
console. A successful deployment ends with `[SP-DEPLOY] [DONE]` and
`errors: []`.

## Optional demonstration

Add `--seed` to the build command and the bundle gains `demo-data.js.txt`.
Paste `deploy.js.txt` first, then `demo-data.js.txt`, from the same bundle.
It creates five `[DEMO]` patterns and sixteen `[DEMO]` asks. Dates are
offsets from the day of the paste, so the picture below holds whenever it is
run. What to look for:

- **Needs response** shows two asks. One was captured ten days ago and its
  *Acknowledge by* is red; the other was captured two days ago and is not.
- **Exploring** shows three asks: two under *Now* and one under *Strategic*.
  The *Priority Score* bar is longest on the Awaiting decision ask (Game
  change x Moderate, 6) and takes its colour from *Value*.
- **Delivery and adoption** shows one Accepted ask under each of two
  patterns. The *Adoption Check Due* on the feedback-cards ask is three days
  past and red.
- **Closed and routed** holds nine rows: one Adopted with a filled *Days To
  Adopted* bar and its *Adoption Note*, one Not adopted, five Routed (one per
  route out), one Duplicate and one Not now with its *Reopen trigger*
  visible.
- **Catalogue** shows one Available pattern with a filled *Days To
  Available* bar (50 of 90) and a *Next Review Due* about eleven months
  out.
- **In build** shows three patterns, one each at Proposed, Building and
  Piloting. **Retired** shows one.
- **By area** holds every open ask, collapsed under its Service Area.

Every person column resolves to whoever pastes the script. Delete the demo
rows before active use: each Title begins with `[DEMO]`, they are matched by
Title on re-paste, and `rollback.js.txt` asks per list before deleting. Do not
seed a site that already holds real asks.

## Verification checklist

### Security

- [ ] Both lists have broken inheritance and exact ACL reconciliation.
- [ ] On `DI_Opportunity`, `DI Champions` and `DI Digital Team` hold
      `DI Contribute No Delete`; on `DI_Pattern`, `DI Champions` hold `Read`
      and `DI Digital Team` hold `DI Contribute No Delete`. On both lists,
      `dbml List Administrators` hold Full Control, Site Members hold `Read`,
      Site Owners hold `Contribute` and `dbml Enterprise Readers` hold `Read`.
- [ ] A test account in `DI Champions` can add an ask and edit it, and
      cannot delete it. The same account can read `DI_Pattern` and cannot add
      a pattern.
- [ ] The same champion account can open an ask another account created and
      edit its digital-team fields. That is the declared model, not a defect:
      the level does not trim by item, and `50-govern/governance.md` says the
      role split is a working rule. Versioning is on, so the edit is visible.
- [ ] A champion account can save a personal view on **Needs response** and
      create an alert on it.
- [ ] A test account in `DI Digital Team` can add and edit rows on both
      lists and cannot delete on either. A Site Owner can delete: the
      associated owner group holds the built-in Contribute, as in every
      family, and `50-govern/governance.md` says who can delete and why the
      no-delete promise covers only the two family groups.
- [ ] A plain Site Member can read both lists, including the demo Not now
      row, and cannot add to either.
- [ ] The header link opens the published capture guide.

### Intake

- [ ] **Needs response** is the default view on `DI_Opportunity`, sorted
      oldest first.
- [ ] The New form shows the **What we heard** fields and nothing from the
      later sections. *Captured Date* is absent from it. **System** holds
      only calculated columns, which never render on entry forms, so it
      shows as a bare heading there; cosmetic and expected. Status saves as
      Captured and Captured Date fills with today.
- [ ] The nine typed controls on the New form are Title, Problem Statement,
      Service Area, Team or unit, Current Method, People Affected, Heard at,
      Data Sensitivity and Requested for. The digital team's fields are not
      on it.
- [ ] Editing a saved ask shows **Triage and score**, **Decision and
      delivery** and **Adoption**; **System** is a bare heading on the edit
      form too. *Value*, *Ease*, *Evidence*,
      *Review Tier* and *Horizon* appear only once Triage Outcome is
      *Explore here*; *Clinical Reviewer* and *Clinical Review Date* once
      Review Tier is *Clinical or data review* or Data Sensitivity is
      *Touches patient or clinical workflow data*.
- [ ] A Captured Date in the future is refused. The refusal shows the list
      message: date-versus-today rules are hoisted onto the list rule at
      build time, and `deploy-manifest.md` names the two that were (Captured
      Date and Decision Date). Acknowledged, Clinical Review and Adopted
      dates carry no future-date rule; the list formula's 1023-character
      ceiling went to the acknowledgement and clinical gates instead.

### Triage and score

- [ ] Setting Status to Exploring with no Triage Outcome, or with no
      Acknowledged Date, is refused with the list message, which begins
      "Check this stage".
- [ ] Setting Status to Awaiting decision with any of *Value*, *Ease*,
      *Evidence* or *Horizon* empty is refused with the same message.
- [ ] Setting Status to Accepted on an ask whose Review Tier is *Clinical or
      data review* and whose Clinical Review Date is empty is refused.
      Filling the date lets it save. Changing the Review Tier to *Standard*
      does not: the gate also reads Data Sensitivity, so an ask marked
      *Touches patient or clinical workflow data* is refused until the date
      is filled whatever the tier says.
- [ ] Setting Status to Accepted straight from Exploring with any of *Value*,
      *Ease*, *Evidence* or *Horizon* empty is refused.
- [ ] Setting Status to Not now with *Reopen trigger* or *Decision Date*
      empty is refused. A trigger of 15 characters or fewer is refused by the
      column's own message.
- [ ] Setting Status to Routed or Duplicate with *Receiving reference* empty
      is refused. On a Duplicate it names the earlier ask.
- [ ] *Priority Score* renders as a bar out of 9 and takes its colour from
      *Value*, so Tweak x Easy (3) and Game change x Hard (3) render at the
      same length in different colours.
- [ ] *Priority Band* reads Later for 1 to 2, Consider for 3 to 4 and
      Prioritise for 6 to 9.
- [ ] *Acknowledge by* is red on the overdue demo ask in **Needs response**
      and is not red on any row that has left Captured.
- [ ] **Exploring** groups on *Horizon* and sorts by *Priority Score*
      descending within each group.

### Delivery and adoption

- [ ] **Delivery and adoption** groups on *Pattern* and holds only Accepted
      rows. Build progress is read from the pattern's own Status.
- [ ] *Sponsor* appears from Awaiting decision on; *Pattern* appears from
      Accepted on; *Adoption Check Due* appears on Accepted rows only.
- [ ] Setting Status to Adopted with *Adopted Date* or *Adoption Note*
      empty is refused. A note of 10 characters or fewer is refused by the
      column's own message.
- [ ] *Days To Adopted* renders as a bar out of 120 on the Adopted demo row.
- [ ] **Closed and routed** holds every Adopted, Not adopted, Routed,
      Duplicate and Not now row, newest change first.

### Patterns

- [ ] **Catalogue** is the default view on `DI_Pattern` and holds Available
      patterns only, by title.
- [ ] Setting Status to Available with *Available Date* empty is refused
      with the pattern list message. Setting it to Retired with *Retired
      Date* or *Retired Reason* empty is refused with the same message.
- [ ] *Next Review Due* reads twelve months after *Available Date* and
      cannot be edited. *Days To Available* renders as a bar out of 90,
      coloured by *Effort Band*.
- [ ] **In build** groups on *Build Owner*. **Retired** sorts by *Retired
      Date*, newest first.
- [ ] List Settings shows the declared indexes: Status, Service Area, Triage
      Outcome, Captured Date, Horizon and Adoption Check Due on
      `DI_Opportunity`; Status, Readiness and Available Date on
      `DI_Pattern`.
- [ ] As a Site Owner, changing a deployed column's type or choices is
      refused (sealed), and List settings offers no "Delete this list".

## Manual steps a redeploy does not check

The deployer neither sets nor verifies the following. Do them by hand on
both lists after the paste and again after any redeploy, because a redeploy
cannot see whether they are still in place.

1. Open **List settings -> Advanced settings** and set **Attachments to list
   items** to **Disabled**. Nothing in this log should be a file; a guide or
   a receiving record is a link.
2. Optionally set **Allow comments on list items** to the service's policy.
   Comments are a clarification channel under the same no-identifiers rule
   as the Problem Statement.

## Rollback boundary

`rollback.js.txt` removes `DI_Opportunity` and `DI_Pattern` after a
per-list confirmation. The `DI Champions`, `DI Digital Team`,
`dbml List Administrators` and `dbml Enterprise Readers` groups remain, as
do their members. Asks that were routed to a helpdesk, an improvement
register, a project pipeline or a mandated system live in those systems and
are unaffected. Use rollback on demonstration or empty deployments only;
real asks are organisational records and are exported first.

## Enterprise reporting access

This family's declared grants are: Site Members read both lists;
`DI Champions` hold `DI Contribute No Delete` on `DI_Opportunity` and `Read`
on `DI_Pattern`; `DI Digital Team` hold `DI Contribute No Delete` on both.
The reporting group below sits beside those grants and changes none of them.

The deploy declares the `dbml Enterprise Readers` site group (shared with every
other family deployed to the site) and grants it `Read` on every list in this
family. The group starts empty only if no family has deployed to the site yet;
it gains a member when any family's build is run with `--enterprise-reader
<account>`, which enrols exactly that one account and nothing else.
`rollback.js.txt` does not remove it: rollback deletes lists, not site groups
or role assignments, so the group and any account enrolled in it survive a
rollback.

A later build that omits the flag does not put the group back to empty:
enrolment only runs when `--enterprise-reader` is given, so an account enrolled
by an earlier build (of this family or any other sharing the site) keeps its
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
`Use Remote Interfaces` intact at web scope. Publishing sites (where
lockdown mode is on by default) and the reporting client's own list
enumeration are still unverified, so the end-to-end path (Power BI or any
other API client) is not yet proven. See the danger block in the mapping
reference's Security section.
