# Deploying compliance obligations (administrator)

Shared procedure: [`templates/README.md`](../../README.md) with
`<name> = compliance-obligations`. Template-specific notes below.

## Before you build

- [ ] `CO_` prefix free on the target site.
- [ ] The obligation-grain guidance in `40-adopt/STAFF-GUIDE.md` read by
      whoever will load the register — grain decided before loading, not
      during.
- [ ] You know who forms **CO Compliance Coordinators**.

## After the paste — verification checklist

- [ ] `CO_Obligation` exists; `SourceInstrument`, `Owner` and `ReviewDate`
      are required.
- [ ] As an ordinary Member: read-only.
- [ ] **Load the obligations** — start with ONE source (your accreditation
      standard, or one act) end-to-end rather than a thin layer of
      everything; a complete slice proves the method and becomes the
      pattern for the rest.
- [ ] Populate **CO Compliance Coordinators**; delete any test rows.
- [ ] Even as an owner: changing a deployed column's type, choices or
      settings is refused (sealed) and List settings offers no "Delete
      this list"; a display-name rename is still possible — it is
      drift, reverted and reported at the next re-paste.

## Recommended views

| View | Filter / grouping |
|---|---|
| The gap list | ComplianceStatus = Non-compliant / Partially compliant — the executive view |
| Not yet assessed | ComplianceStatus = Not assessed, by Owner |
| Reviews due | ReviewDate ≤ today+60 |
| By source | Group by SourceType then SourceInstrument — the accreditation pack |
| By owner | Group by Owner — the "your obligations" view |

## Redeploying

Bump `schema_version`, rebuild, re-paste.
