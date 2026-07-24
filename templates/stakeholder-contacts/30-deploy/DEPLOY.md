# Deploying stakeholder contacts (administrator)

Shared procedure: [`templates/README.md`](../../README.md) with
`<name> = stakeholder-contacts`. Template-specific notes below.

## Before you build

- [ ] `SC_` prefix free on the target site.
- [ ] `OrgType`/`InteractionType` enums fit your stakeholder landscape.
- [ ] **Privacy check**: site membership is scoped to the relationship-
      holding teams; the privacy rules in `50-govern/GOVERNANCE.md` have an
      owner.

## After the paste — verification checklist

- [ ] `SC_Organisation`, `SC_Contact`, `SC_Interaction` exist, created in
      that order (the lookup chain requires it).
- [ ] Create a test organisation → a test contact in it (Organisation
      lookup offers it) → a test interaction with them (Contact lookup
      offers them).
- [ ] `Contact.IsActive` defaults to **Yes**.
- [ ] Any Member can create all three.
- [ ] Delete the test rows (interaction → contact → organisation).
- [ ] Even as an owner: changing a deployed column's type, choices or
      settings is refused (sealed) and List settings offers no "Delete
      this list"; a display-name rename is still possible — it is
      drift, reverted and reported at the next re-paste.

## Recommended views

| List | View | Filter / grouping |
|---|---|---|
| Interaction | Recent activity | Sorted by InteractionDate, newest first |
| Interaction | By contact | Filter by Contact — the handover view |
| Contact | Active by organisation | IsActive = Yes, group by Organisation |
| Organisation | By owner | Group by Owner — who owns which relationship |

## Redeploying

Bump `schema_version`, rebuild, re-paste.
