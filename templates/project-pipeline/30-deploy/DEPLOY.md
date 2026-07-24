# Deploying the project pipeline (administrator)

Shared procedure: [`templates/README.md`](../../README.md) with
`<name> = project-pipeline`. Template-specific notes below.

## Before you build

- [ ] `PP_` prefix free on the target site.
- [ ] `CostBand` thresholds match your delegations; `Stage` names match how
      your organisation actually gates work.
- [ ] The gate authority table in `50-govern/GOVERNANCE.md` is agreed.

## After the paste — verification checklist

- [ ] `PP_Proposal` exists.
- [ ] Score spot-checks on a test proposal:
      - Benefit High + Feasibility Easy → **PriorityScore = 9**
      - Benefit Medium + Feasibility Moderate → **4**
      - Benefit Low + Feasibility Hard → **1**
      - Clear Benefit → score goes **blank** (unscored is visible).
- [ ] Any Member can create and edit proposals.
- [ ] **Load the known backlog** — the wish-list everyone half-remembers
      goes in as Idea/Scoping rows now, or the pipeline starts life
      incomplete and stays that way.
- [ ] Delete the test row.
- [ ] Even as an owner: changing a deployed column's type, choices or
      settings is refused (sealed) and List settings offers no "Delete
      this list"; a display-name rename is still possible — it is
      drift, reverted and reported at the next re-paste.

## Recommended views

| View | Filter / sort |
|---|---|
| The funnel | Stage ≠ Delivered/Declined, group by Stage |
| Decision queue | Stage = Ready for decision, sorted by PriorityScore desc |
| Portfolio | Stage = Approved/In delivery, group by Sponsor |
| Graveyard (yes, keep it) | Stage = Declined/Parked, newest first — institutional memory |

## Redeploying

Bump `schema_version`, rebuild, re-paste. Changing the scoring formula
re-scores every row instantly — treat score changes as a governance event.
