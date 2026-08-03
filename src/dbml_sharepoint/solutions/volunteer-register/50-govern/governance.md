# Volunteer register — governance

## Ownership

| Role | Held by | Accountable for |
|---|---|---|
| Programme owner | *(e.g. volunteer manager / community engagement lead)* | The role matrix, privacy rules, this document |
| VL Volunteer Coordinators | The maintaining group | Records, sweeps, onboarding gates |

## Check requirements by role (edit to your jurisdiction and context)

| Role type | Police check | WWCC (or equivalent) | Induction |
|---|---|---|---|
| Patient/client-facing (wards, transport, home visits) | Required, 3-yearly | Required if role involves children or per your policy | Required before start |
| Retail / op-shop / events | Required, 3-yearly | If children involved | Required |
| Remote/admin support | Per your policy | Per role | Required |

The matrix is the **gate to Active status** — no complete checks, no
start. Jurisdictional names differ (WWCC / Blue Card / WWVP): re-label the
columns to yours before first deploy, not after (`display_names.overrides`
in `20-configure/mapping.yaml` — see `30-deploy/deploy.md`).

### What is enforced at save, and what stays a governance check

The list refuses a save for the two parts of the gate a formula can hold.
It cannot hold the rest, and the difference is worth knowing precisely
rather than assuming the software has your back:

| Rule | Where it lives | Why there |
|---|---|---|
| An induction date cannot be in the future | **Enforced at save**, on the column, with its own message | It reads only its own column, so it can carry a message that names the actual mistake |
| An **Active** volunteer must have an induction date and a start date | **Enforced at save**, on the list | Cross-column, so it shares the list's single validation formula. These two are the only requirements the matrix states for *every* role type |
| **Which** checks a role requires | **Governance check** | The requirement varies by role and lives in the table above. SharePoint cannot read it, and a formula that guessed would be wrong for some roles in both directions |
| Whether a recorded check has actually been sighted | **Governance check** | Nothing in a date field distinguishes a sighted check from a typed one. Coordinators certify it at every status change |
| Whether an expiring check has been chased | **Governance check** | The *Checks expiring 90 days* view is the surface; acting on it is the monthly sweep |

The compensating control for the two rows that stay governance checks is
the *Missing checks* view, which is deliberately **wider than the matrix**
— it surfaces every active volunteer missing police check, WWCC *or*
induction, and the coordinator applies the matrix to the result.

## Privacy (load-bearing — this register holds personal data)

1. Site membership: coordinators and owners only. General staff get
   volunteer information from coordinators, not from the register.
2. Record the minimum: check dates and numbers, not document copies;
   an emergency contact name and phone, nothing more; no health,
   financial or family information — if a volunteer shares relevant
   health context, it's handled per your people processes, not typed
   into Notes.
3. **Exited volunteers**: after your retention period (align with your
   volunteer/HR policy — commonly 7 years for the fact of service, far
   less for the detail), trim rows to name, role, dates; clear check
   numbers, emergency contact and Notes.
4. Subject access applies — coordinators handle requests with your
   privacy officer.

## Cadences

- **Monthly**: the check-expiry sweep (the programme's core control) —
  the *Checks expiring 90 days* and *Missing checks* views.
- **Quarterly**: programme owner reviews the *Active by team* view
  (insurance and funding returns read straight off it) and the *Pipeline*
  view for stalled onboarding.
- **Annually**: role matrix review; retention trim run from the *Inactive
  and exited* view.

## Data-quality rules

1. Active status is impossible without the matrix's checks recorded and
   in date — the list enforces the induction date and the start date at
   save; coordinators certify the rest at every status change.
2. Stand-downs for expired checks are recorded factually and kindly.
3. Exited rows are trimmed on schedule, not hoarded.

## Lifecycle

This register (with onboarding and stakeholder-contacts) is one where
**deletion is expected**: retention rules above, not keep-everything.
Export judiciously (exports inherit the same privacy duties); never run
`rollback.js.txt` against real rows.
