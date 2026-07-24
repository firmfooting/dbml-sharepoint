# Deploying the delegations register (administrator)

Shared procedure: [`templates/README.md`](../../README.md) with
`<name> = delegations-register`. Template-specific notes below.

## Before you build

- [ ] `DG_` prefix free on the target site.
- [ ] The current instrument of delegation is at hand — the register is
      loaded FROM it, clause by clause; it never invents an authority.
- [ ] You know who forms **DG Governance Coordinators**.

## After the paste — verification checklist

- [ ] `DG_Delegation` exists; `RoleHolder`, `SourceInstrument` and
      `ReviewDate` required.
- [ ] As an ordinary Member: read-only.
- [ ] **Load from the instrument** — one row per delegable authority,
      role-not-person, limits and conditions in the instrument's own
      wording. Where the transcription feels ambiguous, that's a finding
      about the instrument: note it for the next instrument review rather
      than smoothing it over.
- [ ] Populate **DG Governance Coordinators**; delete any test rows.
- [ ] Even as an owner: changing a deployed column's type, choices or
      settings is refused (sealed) and List settings offers no "Delete
      this list"; a display-name rename is still possible — it is
      drift, reverted and reported at the next re-paste.

## Recommended views

| View | Filter / grouping |
|---|---|
| By area | Status = Current, group by DelegationArea — the working lookup |
| By role | Status = Current, group by RoleHolder — "what can this role approve?" |
| Reviews due | ReviewDate ≤ today+90 |
| History | Status = Superseded — the audit trail of authority over time |

## Redeploying

Bump `schema_version`, rebuild, re-paste.
