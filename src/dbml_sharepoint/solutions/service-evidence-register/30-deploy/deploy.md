# Deploying the service evidence register

Shared procedure: [`templates/README.md`](../../README.md), with
`<name> = service-evidence-register`. Assess the target, review the generated
manifest, deploy, confirm the manual Advanced settings, then verify with
separate accounts. Do not populate access groups until every go-live gate
below passes.

## Before building

- [ ] Confirm the site is appropriate for information that characterises
      another organisation's performance. This register is discoverable under
      freedom-of-information and legal process; see
      [`50-govern/governance.md`](../50-govern/governance.md).
- [ ] Replace `service_domain` in `10-design/schema.dbml` with your own
      service breakdown. Stable names matter more than a detailed taxonomy.
- [ ] Trim `failure_mode` to the failures that can actually occur in your
      arrangement. Do not add members after go-live if you can avoid it.
- [ ] Decide how `Provider` is written and record the exact spelling in your
      local guidance. Every grouped and filtered view depends on it being
      consistent.
- [ ] Name one register owner and a small curator group. Curators are the
      only people who see `ServiceIssue`.
- [ ] Agree the escalation threshold before anyone logs anything. The shipped
      default is *past Response Due Date, chased twice or more, still
      unresolved*. governance.md explains why, so you can move it deliberately.
- [ ] Confirm `SE_` is free on the target site.

There are **no placeholder URLs** in this template's form headers; nothing
here points at an external document, so there is nothing to replace.

## Build

```bash
dbml-sharepoint build \
  --schema 10-design/schema.dbml \
  --mapping 20-configure/mapping.yaml \
  --release 20-configure/release.yaml \
  --site-url https://yourtenant.sharepoint.com/sites/your-site \
  --site-role default \
  --out ./build
```

Review `build/deploy-manifest.md`. Continue only with zero errors and zero
warnings. Run `assess.js.txt` first, then `deploy.js.txt` from an authorised Site
Owner console. A successful deployment ends with `[SP-DEPLOY] [DONE]` and
`errors: []`.

Three lists are created: `SE_ServiceEvent`, `SE_FollowUp` and
`SE_ServiceIssue`.

## Mandatory manual gate

The deployer reconciles permission levels and ACLs, but it cannot configure or
verify SharePoint's Advanced settings. On **`SE_ServiceEvent`** and
**`SE_FollowUp`** (not on `SE_ServiceIssue`, which contributors cannot reach
at all):

1. Open **List settings -> Advanced settings**.
2. Leave **Read access** on **Read all items**. This register does *not* use
   read-own item-level filtering, and turning it on would break it: it filters
   Curators too, and the **Needs review** queue is by construction made of
   rows Curators did not create. A contributor seeing a colleague's event is
   not a leak here. The sensitive list is `SE_ServiceIssue`, and they cannot
   open it.
3. Leave **Create and Edit access** on **Create and edit all items**. A
   contributor still cannot alter a saved record (which is what makes the
   record worth having) because the assigned `SE Log Only` level withholds
   Edit outright. The permission level carries that property, so the
   item-level setting is not needed to buy it and would only strip Curators of
   the updates they are asked to make.
4. Leave **Attachments to list items** **Enabled**. Unlike a register holding
   personal information, this one *wants* the artefact stored beside the row:
   *Attached to this record* is the strongest value of Evidence Held.
5. Save the settings.
6. Add two temporary test users to **SE Evidence Contributors**. Keep them out
   of Curators and Administrators.
7. User A creates event A; User B creates event B.
8. User A adds a follow-up against event A; User B adds one against event B.
   `SE_FollowUp` carries the same grant and the same claim in the checklist,
   so testing only the event list would leave half the gate unverified.
9. Verify neither user can edit or delete **any of the four rows**, their own
   included. That refusal is the whole point of the group. Verify a Curator
   can open and update all four.
10. Verify **neither test user can open `SE_ServiceIssue` at all**: not the
    list, not a view, not an item.
11. Remove the test rows and users. Only now add real contributors.

If any step fails, remove contributors from the group and do not go live.
Repeat this two-account test after permission changes or major tenant
configuration changes.

## Optional demonstration

Add `--seed` to the build command. `demo-data.js.txt` creates fifteen rows: six
events, five follow-ups and four themes, all prefixed `[DEMO]`. They tell one
deliberately mundane, sector-neutral story (a recurring access-provisioning
failure, chased four times, escalated, partly remedied) and are chosen so
every declared view returns something and every formatted column is seen to
render, including an event marked **Not substantiated**.

Use seed data only on a demonstration site or before real logging begins.
Delete the rows before go-live.

## Verification checklist

### Security and boundaries

- [ ] All three lists have broken inheritance and exact ACL reconciliation.
- [ ] Only **SE Evidence Contributors**, **SE Evidence Curators**,
      **dbml List Administrators** and **dbml Enterprise Readers** hold declared
      direct grants on `SE_ServiceEvent` and `SE_FollowUp`. Associated Site
      Members and Site Owners have no declared list grant on any of the three.
- [ ] **`SE_ServiceIssue` grants nothing to Contributors**: only Curators
      (Contribute), Administrators (Full Control) and dbml Enterprise Readers
      (`Read`).
- [ ] Contributors hold `SE Log Only`; Curators hold Contribute;
      Administrators hold Full Control.
- [ ] Both contributor lists are on **Read all items** and **Create and edit
      all items**. Read-own filtering would apply to Curators as well and
      empty the **Needs review** queue; `SE Log Only` already withholds Edit,
      so nothing is gained by turning it on.
- [ ] The mandatory two-account test passes on both contributor lists.
- [ ] Sealed columns and list-deletion protection are enabled on all three.

### Capture experience

- [ ] **Outstanding and ageing** is the default view on `SE_ServiceEvent`. On
      a fresh site it is empty, which is correct.
- [ ] The New event form shows **What happened**, **How you know** and
      **Impact**, plus *Raised with provider*. Status, the reviewer's fields
      and the theme lookup are absent.
- [ ] With **Event Nature** on *Single occurrence*, **Response Due Date** and
      **Last Followed Up** do not appear. Change it to *Unactioned request or
      ticket* and both appear: on the New form, not only on a saved record,
      because the person logging the request is the one who knows when a
      response was promised and cannot edit afterwards.
- [ ] **Resolved Date** and **Outcome for us** appear whatever the Event
      Nature. A single occurrence can still be resolved.
- [ ] Saving an *Unactioned request or ticket* with no **Provider Reference**
      is refused, with the message about a complaint that cannot say which
      request.
- [ ] Setting Status to **Accepted** on a row that is both *reported to me by
      a colleague* and *None - recollection only* is refused.
- [ ] The **Resolved Date** / **Outcome for us** pair is refused in both
      directions: a date with no outcome, and an outcome of *Resolved
      satisfactorily*, *Resolved after escalation* or *Worked around locally*
      with no date. *Partially resolved*, *Unresolved* and *Recurred after
      resolution* need no date. They are the honest state of an open row.
- [ ] **An event that happened earlier today saves, and one stamped an hour
      from now is refused.** `Occurred At` is a datetime and its rule compares
      against the instant of the save, not a whole-day bound, so the
      refusal should bite within the hour rather than at midnight. A date
      next month is refused too.
- [ ] `Logged Date` defaults to today without user entry.

### The calculated columns, and the one that is blank on purpose

- [ ] An event logged the day it happened shows **Days To Log** 0 and
      **Record Timeliness** *Same day*, in green. One logged five weeks later
      shows *Retrospective*, in red.
- [ ] **`Days Outstanding` is blank on an open row. This is correct.**
      SharePoint refuses `[Today]` in a calculated column, so a stored live
      age is not available. The live ageing is the *Outstanding and ageing*
      view (its filter is evaluated at query time) and the red on **Response
      Due Date** (compared against `@now` when the page renders). Fill in a
      Resolved Date and the column populates.
- [ ] A `FollowUp` with a response shows **Days To Respond**; one without is
      blank.
- [ ] A `ServiceIssue` that has been raised and answered shows **Days To
      Response**.

### Lookups and views

- [ ] A `FollowUp` row shows its parent event in **Event or request**, and the
      **By event** view groups by it and collapses.
- [ ] An Accepted or Escalated event shows its theme in **Part of theme**, and
      the **Evidence pack** view groups by it.
- [ ] **By failure mode** and **Evidence pack** each show a **Hours Lost**
      total under every group.
- [ ] The **Open issues** view applies the row wash to an issue whose
      Materiality is *Critical to service*, and to nothing else. This is the
      template's only row-level signal.
- [ ] Five authored views exist on `SE_ServiceEvent` (Outstanding and ageing,
      Needs review, By failure mode, Evidence pack, Closed and not
      substantiated), five on `SE_FollowUp` (Awaiting a response, By event,
      Escalation trail, Closed without resolving, Recent follow-ups) and four
      on `SE_ServiceIssue` (Open issues, Awaiting response, Remedies due,
      Concluded). The generated **All Items** recovery view is hidden from the
      modern view bar on each.

### Operating model

- [ ] Somebody owns the **Needs review** queue, and it is worked at a stated
      cadence rather than when a review is imminent.
- [ ] The escalation threshold is written down and known to the curators.
- [ ] **Curators** know that `Last Followed Up` on the event is carried across
      as part of the weekly chase. It is the template's one hand-maintained
      link, a contributor can only have set it when the event was created, and
      the **By event** view is how you check it.

## What the save rules cannot enforce, and why

SharePoint refuses a validation formula that references a **multi-line**
column. The build reports it as an error rather than leaving it to fail on a
live tenant, so several rules that would otherwise be here are absent by
platform constraint rather than by choice:

- an event has **no minimum length** on *The account*;
- **Not substantiated** does not require a reviewer's assessment;
- a theme's *Response received*, *Remedy agreed* and closure stages require
  their **dates** but not their narrative text.

Each stage is gated on its date instead, which is the closest honest proxy.
You cannot record a response date without having had a response. The
narrative expectations are carried by the form notes and by the review cadence
in governance.md. Every save message claims only what its formula actually
enforces.

## Rollback boundary

`rollback.js.txt` is for empty or demonstration deployments only. Real rows are
organisational records, and a register assembled for a service review is
exactly the kind of thing whose deletion needs to be a deliberate, authorised
act: export it and follow your records schedule before any decommission.
Deletion protection is UI friction, not authority to destroy data.

## Enterprise reporting access

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
it is manual. Clear it in Site permissions > Groups.

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
