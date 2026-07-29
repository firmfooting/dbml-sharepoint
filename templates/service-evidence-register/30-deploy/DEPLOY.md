# Deploying the service evidence register

Shared procedure: [`templates/README.md`](../../README.md), with
`<name> = service-evidence-register`. Assess the target, review the generated
manifest, deploy, apply the manual item-level setting, then verify with
separate accounts. Do not populate access groups until every go-live gate
below passes.

## Before building

- [ ] Confirm the site is appropriate for information that characterises
      another organisation's performance. This register is discoverable under
      freedom-of-information and legal process; see
      [`50-govern/GOVERNANCE.md`](../50-govern/GOVERNANCE.md).
- [ ] Replace `service_domain` in `10-design/schema.dbml` with your own
      service breakdown. Stable names matter more than a detailed taxonomy.
- [ ] Trim `failure_mode` to the failures that can actually occur in your
      arrangement. Do not add members after go-live if you can avoid it.
- [ ] Decide how `Provider` is written and record the exact spelling in your
      local guidance. Every grouped and filtered view depends on it being
      consistent.
- [ ] Name one register owner and a small curator group. Curators are the
      only people who see `ServiceIssue`.
- [ ] Agree the escalation threshold before anyone logs anything — the shipped
      default is *past Response Due Date, chased twice or more, still
      unresolved*. GOVERNANCE.md explains why, so you can move it deliberately.
- [ ] Confirm `SE_` is free on the target site.

There are **no placeholder URLs** in this template's form headers; nothing
here points at an external document, so there is nothing to replace.

## Build

```bash
dbml-sharepoint build \
  --schema templates/service-evidence-register/10-design/schema.dbml \
  --mapping templates/service-evidence-register/20-configure/mapping.yaml \
  --release templates/service-evidence-register/20-configure/release.yaml \
  --site-url https://yourtenant.sharepoint.com/sites/your-site \
  --site-role default \
  --out ./build
```

Review `build/deploy-manifest.md`. Continue only with zero errors and zero
warnings. Run `assess.js` first, then `deploy.js` from an authorised Site
Owner console. A successful deployment ends with `[SP-DEPLOY] [DONE]` and
`errors: []`.

Three lists are created: `SE_ServiceEvent`, `SE_FollowUp` and
`SE_ServiceIssue`.

## Mandatory manual item-level gate

The deployer reconciles permission levels and ACLs, but it cannot configure or
verify SharePoint's item-level Advanced settings. `SE Log Only` relies on
them. On **`SE_ServiceEvent`** and **`SE_FollowUp`** (not on
`SE_ServiceIssue`, which contributors cannot reach at all):

1. Open **List settings → Advanced settings**.
2. Set **Read access** to **Read items that were created by the user**.
3. Set **Create and Edit access** to **Create items and edit items that were
   created by the user**. The assigned `SE Log Only` level still withholds
   Edit, so a contributor can create and read their own record but cannot
   alter it afterwards — which is what makes the record worth having.
4. Leave **Attachments to list items** **Enabled**. Unlike a register holding
   personal information, this one *wants* the artefact stored beside the row:
   *Attached to this record* is the strongest value of Evidence Held.
5. Save the settings.
6. Add two temporary test users to **SE Evidence Contributors**. Keep them out
   of Curators and Administrators.
7. User A creates event A; User B creates event B.
8. Verify each user can open only their own event and cannot edit or delete
   it. Verify a Curator can see and update both.
9. Verify **neither test user can open `SE_ServiceIssue` at all** — not the
   list, not a view, not an item.
10. Remove the test rows and users. Only now add real contributors.

If any step fails, remove contributors from the group and do not go live.
Repeat this two-account test after permission changes or major tenant
configuration changes.

## Optional demonstration

Add `--seed` to the build command. `demo-data.js` creates fifteen rows: six
events, five follow-ups and four themes, all prefixed `[DEMO]`. They tell one
deliberately mundane, sector-neutral story — a recurring access-provisioning
failure, chased four times, escalated, partly remedied — and are chosen so
every declared view returns something and every formatted column is seen to
render, including an event marked **Not substantiated**.

Use seed data only on a demonstration site or before real logging begins.
Delete the rows before go-live.

## Verification checklist

### Security and boundaries

- [ ] All three lists have broken inheritance and exact ACL reconciliation.
- [ ] Only **SE Evidence Contributors**, **SE Evidence Curators** and
      **SE List Administrators** hold declared direct grants on
      `SE_ServiceEvent` and `SE_FollowUp`. Associated Site Members and Site
      Owners have no declared list grant on any of the three.
- [ ] **`SE_ServiceIssue` grants nothing to Contributors** — only Curators
      (Contribute) and Administrators (Full Control).
- [ ] Contributors hold `SE Log Only`; Curators hold Contribute;
      Administrators hold Full Control.
- [ ] The mandatory two-account item-level test passes on both contributor
      lists.
- [ ] Sealed columns and list-deletion protection are enabled on all three.

### Capture experience

- [ ] **Outstanding and ageing** is the default view on `SE_ServiceEvent`. On
      a fresh site it is empty, which is correct.
- [ ] The New event form shows **What happened**, **How you know** and
      **Impact**, plus *Raised with provider*. Status, the reviewer's fields
      and the theme lookup are absent.
- [ ] With **Event Nature** on *Single occurrence*, the four chase fields
      (Response Due Date, Last Followed Up, Resolved Date, Outcome for us) do
      not appear. Change it to *Unactioned request or ticket* and they do.
- [ ] Saving an *Unactioned request or ticket* with no **Provider Reference**
      is refused, with the message about a complaint that cannot say which
      request.
- [ ] Setting Status to **Accepted** on a row that is both *reported to me by
      a colleague* and *None - recollection only* is refused.
- [ ] **An event that happened earlier today saves.** This is the check that
      matters: `Occurred At` is a datetime and SharePoint's `TODAY()` is
      midnight, so the rule uses the `today+1` allowance. If a same-day event
      is rejected, the allowance has been edited out. A date next month is
      still refused.
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
- [ ] Staff know that `Last Followed Up` on the event must be updated when a
      follow-up row is added — it is the template's one hand-maintained link,
      and the **By event** view is how you check it.

## What the save rules cannot enforce, and why

SharePoint refuses a validation formula that references a **multi-line**
column. The build reports it as an error rather than leaving it to fail on a
live tenant, so several rules that would otherwise be here are absent by
platform constraint rather than by choice:

- an event has **no minimum length** on *The account*;
- **Not substantiated** does not require a reviewer's assessment;
- a theme's *Response received*, *Remedy agreed* and closure stages require
  their **dates** but not their narrative text.

Each stage is gated on its date instead, which is the closest honest proxy —
you cannot record a response date without having had a response. The
narrative expectations are carried by the form notes and by the review cadence
in GOVERNANCE.md. Every save message claims only what its formula actually
enforces.

## Rollback boundary

`rollback.js` is for empty or demonstration deployments only. Real rows are
organisational records, and a register assembled for a service review is
exactly the kind of thing whose deletion needs to be a deliberate, authorised
act: export it and follow your records schedule before any decommission.
Deletion protection is UI friction, not authority to destroy data.
