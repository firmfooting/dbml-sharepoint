# Deploying the opportunities register

Shared procedure: [`templates/README.md`](../../README.md), with
`<name> = opportunities-register`. Assess the target, review the generated
manifest, deploy, apply the manual privacy setting, then verify with separate
accounts. Do not populate access groups until every go-live gate below passes.

## Before building

- [ ] Confirm this will be a thin routing layer, not a replacement for clinical
      incidents, enterprise risk, complaints/open disclosure, privacy/cyber,
      emergencies, project controls or delivery systems.
- [ ] Replace `service_area` in `10-design/schema.dbml` with the smallest useful
      local facility/directorate taxonomy. Stable routing names matter more
      than detailed organisational charts.
- [ ] Tailor Triage Outcome and Delivery Route to the systems that actually
      exist. Each route needs an accountable owner and a record identifier.
- [ ] Confirm the health service prohibition on patient identifiers, clinical
      record content and sensitive staff detail in this list.
- [ ] Name one register owner and a small steward group. Use an existing
      quality, improvement, operations or portfolio forum for decisions; do
      not create an opportunities committee.
- [ ] Replace both header placeholders in
      `20-configure/formatting/opportunity-form-header.json`:
      - `https://REPLACE-WITH-URGENT-ROUTING-URL` — the staff-facing page for
        incidents, emergencies, complaints, privacy/cyber and other required
        pathways;
      - `https://REPLACE-WITH-OPPORTUNITY-PROCESS-URL` — the short local triage
        guide and contact.
- [ ] Confirm `OR_` is free on the target site and that this site is appropriate
      for de-identified organisational information.

## Build

```bash
dbml-sharepoint build \
  --schema templates/opportunities-register/10-design/schema.dbml \
  --mapping templates/opportunities-register/20-configure/mapping.yaml \
  --release templates/opportunities-register/20-configure/release.yaml \
  --site-url https://yourtenant.sharepoint.com/sites/your-site \
  --site-role default \
  --out ./build
```

Review `build/deploy-manifest.md`. Continue only with zero errors and zero
warnings. Run `assess.js` first, then `deploy.js` from an authorised Site
Owner/admin console. A successful deployment ends with
`[SP-DEPLOY] [DONE]` and `errors: []`.

## Mandatory manual privacy gate

The deployer can reconcile permission levels and ACLs, but it cannot configure
or verify several Advanced settings. On the new list:

1. Open **List settings → Advanced settings**.
2. Set **Attachments to list items** to **Disabled**.
3. Leave **Allow comments on list items** set to **Yes**. Comments are the
   clarification channel; they are not a place for identifying or sensitive
   material.
4. Set **Read access** to **Read items that were created by the user**.
5. Set **Create and Edit access** to **Create items and edit items that were
   created by the user**. The assigned `OR Submit Only` permission still
   withholds Edit, so submitters can create and read their own record but
   cannot alter it.
6. Save the settings.
7. Add two temporary test users to **OR Opportunity Submitters**. Keep them out
   of the Stewards and Administrators groups.
8. User A creates record A; User B creates record B.
9. Verify each user can open only their own record and cannot edit or delete
   it. Verify a Steward can see and update both.
10. Verify neither test user can add an attachment. Verify each can add a
    comment to their own item and cannot see or comment on the other user's
    item. If the tenant requires broader Edit permission to comment, do not
    grant it: keep comments steward-only and document the local clarification
    channel instead.
11. Remove the test rows and users. Only now add real submitters.

If any step fails, remove submitters from the group and do not go live. Repeat
this two-account test after permission changes, list migration or major tenant
configuration changes.

## Optional demonstration

Add `--seed` to the build command. `demo-data.js` creates nine de-identified
records:

- minimal capture;
- clinical-system redirect with only a safe reference;
- direct hand-off to an existing initiative;
- assessment using an equity/cultural-safety override;
- an overdue routine decision scoring 16;
- accepted hand-off and dated deferral;
- fast screening closure and duplicate closure.

Use seed data only on a demonstration site or before real intake. Every title
starts `[DEMO]`; delete the rows before go-live.

## Verification checklist

### Security and boundaries

- [ ] The list has broken inheritance and exact ACL reconciliation.
- [ ] Only **OR Opportunity Submitters**, **OR Opportunity Stewards** and
      **OR List Administrators** have declared direct grants. Associated Site
      Members and Site Owners have no declared list grant.
- [ ] Submitters hold `OR Submit Only`; Stewards hold `OR Steward No Delete`;
      Administrators hold Full Control.
- [ ] `OR Steward No Delete` includes `Manage Lists`, which SharePoint requires
      for Stewards to see every item despite read-own filtering. It does not
      include Delete Items. Keep the group small and verify sealed columns and
      list-deletion protection remain enabled.
- [ ] The mandatory two-account item-level access test passes.
- [ ] Attachments are disabled and absent from the New and Display experiences.
- [ ] Comments remain enabled. A Submitter can comment only on an item they can
      read; the no-identifiers rule is present in staff guidance. Test users
      cancel any `@mention` prompt that offers to grant wider access.
- [ ] Neither a Submitter nor a Steward can delete a record. A Steward can see
      and update both test users' records.
- [ ] Both form-header links work and open the local approved guidance.

### Intake experience

- [ ] **Needs triage** is the default view.
- [ ] New shows **Stop and route safely** and **Capture once** only.
- [ ] The five required controls are Safety and privacy check, Problem or
      opportunity, Problem Statement, Service or facility area and Source
      Project. Evidence link, Project link and scope boundary remain optional.
- [ ] Status saves as Captured and Identified Date defaults to today without
      user entry.
- [ ] Selecting **Urgent, sensitive or unsure** refuses save and tells the user
      to follow the routing-guide link.
- [ ] The header uses tenant theme classes and clearly says this is not an
      incident, emergency, approval or delivery channel.

### Workflow and fast exits

- [ ] Existing forms have seven sections; assessment fields appear only when
      Triage Route is **Assess here**.
- [ ] A steward can redirect a Captured item by confirming the scope boundary,
      choosing the relevant Triage Route, setting Status to Transferred,
      selecting Delivery Route and adding the receiving record/control ID — no
      benefit assessment is required.
- [ ] Direct hand-off follows the same short path.
- [ ] Duplicate requires a receiving reference but no assessment.
- [ ] Not proceeding can record a screening reason without invented benefit or
      effort values.
- [ ] Awaiting decision, Accepted and Parked refuse save without Benefit Type,
      Benefit Potential, Time Criticality, a non-Unknown Effort Band and a
      Proposed Benefit Measure.
- [ ] Assessing, Awaiting decision, Accepted and Parked require one dated next
      action. Awaiting decision requires Decision Due Date; Accepted/Parked
      require Decision Date; Parked requires Review Due Date.
- [ ] Stewards verify manually that Status and Triage Route tell the same story
      and that owners, authorities, evidence and rationale are credible.

### Score and presentation

- [ ] Limited + Flexible → **1 / Routine**.
- [ ] Material + Within 3 months → **6 / Consider**.
- [ ] Major + Within 3 months → **9 / Prioritise**.
- [ ] System-wide + Time-sensitive → **16 / Prompt decision**.
- [ ] Choosing any Safety, equity or authority override blanks Priority Score
      and shows **Use existing priority**.
- [ ] The **Decisions** row wash uses tenant `themeLighter` styling for Prompt
      decision and Use existing priority; semantic column formatters use the
      shared native SharePoint styles.
- [ ] **Priority Score** appears in **Decisions** as the same shared data-bar
      treatment used for calculated scores in the risk register. An override
      leaves the score blank and uses **Use existing priority** instead.
- [ ] Five authored views exist: **Needs triage**, **Assessments**,
      **Decisions**, **Handoff and deferred**, **Closed and redirected**. The
      generated **All Items** recovery view is hidden from the modern view bar.
- [ ] Exactly eleven schema-declared indexes are present: Status, Service Area,
      Triage Outcome, Source Project, Identified Date, Next Action Due,
      Decision Due Date, Review Due Date, Delivery Route, Benefit Potential and
      Effort Band.

### Operating model

- [ ] The register is a standing agenda item or exception digest in an
      existing forum; no new committee was created.
- [ ] A named steward owns Needs triage, Decisions and Handoff and deferred.
- [ ] Reporting is limited to untriaged, unowned, overdue, waiting for authority
      and repeated system themes; detailed activity reporting has an explicit
      decision use.
- [ ] Project closure guidance points staff to this register without asking
      them to repeat information already held in a controlled system.

## Rollback boundary

`rollback.js` is for empty/demo deployments only. Real rows are organisational
records: export them and follow the health service records schedule before any
decommission. Deletion protection is UI friction, not authority to destroy
data.
