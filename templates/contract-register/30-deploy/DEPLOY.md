# Deploying the contract register (administrator)

Follow the shared procedure in [`templates/README.md`](../../README.md) with
`<name> = contract-register`. This page covers only what is specific here.

## Before you build

- [ ] `CT_` prefix free on the target site? (Site contents — no `CT_*` lists.)
- [ ] `ContractType`/`Status`/`RenewalType` choices match your vocabulary
      (`10-design/schema.dbml`) — renaming choices after data exists strands
      old rows.
- [ ] You know who goes in **CT Contract Managers** (the deploy creates it
      empty; you populate it after).

**Expected manifest finding**: one warning — `Contract.ContractRef: unique
without not_null` — is intentional: the reference is optional, and
uniqueness is enforced on the rows that have one.

## After the paste — verification checklist

- [ ] `CT_Contract` exists; create a test row with StartDate `2026-01-01`,
      EndDate `2027-06-30` → **TermMonths shows 17** automatically.
- [ ] `ContractRef` rejects a duplicate value (unique constraint).
- [ ] As an ordinary site Member: the list is **read-only**.
- [ ] Site permissions → Groups: `CT Contract Managers` (empty — now add
      your contract managers) and `CT List Administrators` (empty — leave
      it empty; the deploy script self-enrols per run).
- [ ] Delete the test row (as a Contract Manager).
- [ ] Even as an owner: changing a deployed column's type, choices or
      settings is refused (sealed) and List settings offers no "Delete
      this list"; a display-name rename is still possible — it is
      drift, reverted and reported at the next re-paste.

## Recommended views to create after deploy

| View | Filter / sort |
|---|---|
| Expiring 90 days | `EndDate` ≤ today+90 and `Status` ≠ Exited, sorted by EndDate |
| Auto-renewals | `RenewalType` = Auto-renews, sorted by EndDate |
| By counterparty | Group by `Counterparty` |

(Views are per-site presentation; the deployer intentionally provisions data
structure, not presentation.)

## Redeploying after a schema change

Edit the DBML/mapping, bump `schema_version` in `release.yaml`, rebuild,
re-paste. Existing rows are untouched; drifted settings are reconciled.
