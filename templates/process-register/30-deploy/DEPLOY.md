# Deploying the process register (administrator)

Shared procedure: [`templates/README.md`](../../README.md) with
`<name> = process-register`. Template-specific notes below.

## Before you build

- [ ] `PR_` prefix free on the target site.
- [ ] `CurrentState` values reflect your actual landscape (name legacy
      systems explicitly if it helps honest answers).
- [ ] The scoring definitions in `50-govern/GOVERNANCE.md` are agreed —
      scores are only comparable if everyone scores the same way.
- [ ] Inventory workshops scheduled (see `40-adopt/STAFF-GUIDE.md`) — an
      empty register deployed without a filling plan stays empty.

## After the paste — verification checklist

- [ ] `PR_BusinessProcess` exists.
- [ ] Score spot-checks on a test process:
      - High criticality + Severe pain → **DigitisationPriority = 9**
      - Medium + Moderate → **4**
      - Low + Minor → **1**
      - Clear Criticality → score goes **blank**.
- [ ] Any Member can create and edit rows.
- [ ] Delete the test row.
- [ ] Even as an owner: changing a deployed column's type, choices or
      settings is refused (sealed) and List settings offers no "Delete
      this list"; a display-name rename is still possible — it is
      drift, reverted and reported at the next re-paste.

## Recommended views

| View | Filter / sort |
|---|---|
| The worklist | DigitisationStatus ≠ Digitised / Not worth digitising, sorted by DigitisationPriority desc |
| Programme dashboard | Group by DigitisationStatus |
| By function | Group by Function — workshop and review unit |
| Key-person risk | CurrentState = Spreadsheet or Paper/manual, Criticality = High |

## Redeploying

Bump `schema_version`, rebuild, re-paste. Score-definition changes re-score
every row — recalibrate deliberately, not casually.
