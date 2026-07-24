# Deploying the credentialing register (administrator)

Shared procedure: [`templates/README.md`](../../README.md) with
`<name> = credentialing-register`. Template-specific notes below.

## Before you build

- [ ] `CR_` prefix free on the target site.
- [ ] `Discipline`/`CredentialType` enums match your workforce.
- [ ] **Privacy check**: site membership reviewed — the register holds
      staff professional data and the visibility decision in
      `50-govern/GOVERNANCE.md` is made and recorded.
- [ ] You know who forms **CR Credentialing Coordinators**.

**Expected manifest finding**: one warning — `Practitioner.RegistrationNumber:
unique without not_null` — is intentional: non-registered credentialed
roles have no registration number, and uniqueness is enforced on the rows
that do.

## After the paste — verification checklist

- [ ] `CR_Practitioner` and `CR_Credential` exist (Practitioner first).
- [ ] Create a test practitioner; add a credential against them (the
      Practitioner lookup offers the row); `RegistrationNumber` rejects a
      duplicate.
- [ ] As an ordinary Member: read-only.
- [ ] **Load the workforce** — the register is only trustworthy complete:
      every credentialed practitioner, their current scope decision and
      review date, then their credentials with expiries. Budget real time
      for this; it is the project.
- [ ] Populate **CR Credentialing Coordinators**; delete the test rows.
- [ ] Even as an owner: changing a deployed column's type, choices or
      settings is refused (sealed) and List settings offers no "Delete
      this list"; a display-name rename is still possible — it is
      drift, reverted and reported at the next re-paste.

## Recommended views

| List | View | Filter / sort |
|---|---|---|
| Practitioner | Registrations expiring | RegistrationExpiry ≤ today+90, Status = Current |
| Practitioner | Scope reviews due | ScopeReviewDate ≤ today+60 |
| Practitioner | By discipline | Group by Discipline |
| Credential | Expiring credentials | ExpiryDate ≤ today+90, Status ≠ Expired/Withdrawn |
| Credential | Per practitioner | Filter by Practitioner — the credentialing-file view |

## Redeploying

Bump `schema_version`, rebuild, re-paste.
