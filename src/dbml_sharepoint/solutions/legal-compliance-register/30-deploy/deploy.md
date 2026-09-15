# Deploying legal compliance register (administrator)

Shared procedure: [solution deployment](../../README.md), using
`legal-compliance-register`. The library is **Legislative Compliance**, with
URL name `LegislativeCompliance`. Assess the site, review the generated manifest,
paste the deploy script, then verify the resulting library.

## Before you build

- [ ] Confirm that **Legislative Compliance** and URL name
      `LegislativeCompliance` are available.
- [ ] Customise the DBML `division` enum and `entities.Document.folders` in the
      mapping together. Update every `demo_items.Document` entry's `file.folder`
      and `values.Division` to the same divisions before building with `--seed`.
- [ ] Replace the three sample values in the DBML `oversight_committee` enum
      with the organisation's committees. The column is optional.
- [ ] Identify the platform owners, division executives and business owners.
      The platform owner assigns the executive manually based on the folder;
      the executive then assigns the business owner.
- [ ] Agree the site's sharing settings. The mapping uses exact permission
      reconciliation; inspect the generated manifest before deploying.
- [ ] Plan browser-based use. Microsoft's [OneDrive read-only guidance](https://learn.microsoft.com/en-us/troubleshoot/sharepoint/lists-and-libraries/files-open-as-read-only-and-cannot-check-in-or-out)
      describes the sync restriction for libraries with validation.

## Build and demonstrate

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

Paste `assess.js.txt`, review `deploy-manifest.md`, then paste `deploy.js.txt`.
For a demonstration, paste `demo-data.js.txt` afterwards. It creates nine
synthetic files: eight SAQs and one REG across all four example divisions.
Two vendor issues share a topic but have different periods.
Both the reviewed and unreviewed recording routes
are represented. No uploaded organisation data is part of the demo.

The family declares one business library. Standard deployment logging is
separate infrastructure; use the build's `--no-sidecars` option if local
logging sidecars are not wanted.

## Verification checklist

- [ ] **Legislative Compliance** exists at `LegislativeCompliance` as a
      document library with the declared folders.
      No Topic list is declared by this version.
- [ ] All ten views in the family README exist. **Pending** is the default.
      **Folder View** preserves the folder layout; assessment worklists find
      files across the division folders.
- [ ] **Platform owner** is flat and unfiltered, includes SAQs and REGs across
      folders, and shows recently modified files first. An upload with missing
      assignments remains visible here.
- [ ] The header names the topic. The form sections are **The document**,
      **Assign and complete**, **Optional executive review** and **Record
      in the portal**.
- [ ] Set Type to *REG*: assessment fields hide. The file appears in
      **Reference regulations** and no assessment worklist.
- [ ] Upload a vendor SAQ issued in Q3 2023. **Issued year**
      and **Issued quarter** do not prefill from the upload date. Enter 2023
      and Q3; the issuance-year rule accepts it.
- [ ] Try moving an SAQ to *In progress* without its topic or division.
      The save rule refuses the change.
- [ ] Try *Complete* without a completed date. The save rule refuses it.
- [ ] Clear **Status** on an SAQ, or clear **Review requirement** on a Complete
      SAQ. The save rule refuses both; REGs can leave these fields blank.
- [ ] Reopen a completed SAQ as *In progress* without clearing its completion
      date. The save rule refuses it; clear the date in the same save.
- [ ] Upload a REG and classify it as *REG*. **Status** and **Review requirement**
      have no defaults and stay blank. Choose these values explicitly for SAQs.
- [ ] Complete an SAQ with review *Not required*. It appears in **To record
      in the portal** without a reviewed date.
- [ ] Complete one with review *Required*. It appears in **Awaiting review**
      and cannot record a portal date until a reviewed date is entered.
- [ ] Set the recording date on a ready SAQ. It leaves **To record in the
      portal** and appears in **Recorded assessments**.
- [ ] Future completion, review and recording dates are refused on SAQs.
- [ ] **LC Assessment Owners** can edit workbooks and metadata without
      deleting files. **LC Compliance Coordinators** can maintain files;
      ordinary site members have Read.
- [ ] Sealed columns and library deletion protection are enabled. Verify
      with the generated verification script after the deploy.

These checks include rendered behaviour. A successful build or JSON readback
alone does not establish that a library form or view works as intended.

## Manual adoption settings

The deploy creates folders; it does not set folder metadata defaults or map
folders to people. In Library settings, configure **Column default value
settings** for Division per folder and verify a test upload. The platform
owner still checks the division and assigns the corresponding executive.
When moving an open assessment, check those assignments again.

Apply the organisation's retention label and enable Document ID if required
by its records policy. Decide whether to hide the New Folder command and
leave document opening configured for browser use. These manual settings
are not reconciled by redeployment.

Populate **LC Compliance Coordinators** and **LC Assessment Owners**. Remove
the synthetic demonstration files before filing production assessments.

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
