# Deploying the onboarding tracker (administrator)

Shared procedure: [`templates/README.md`](../../README.md) with
`<name> = onboarding-tracker`. Template-specific notes below.

## Before you build

- [ ] `OB_` prefix free on the target site.
- [ ] `TaskFunction` enum matches the teams that actually onboard people.
- [ ] **Privacy check**: the site's membership is scoped to onboarding
      participants (starter records are personal data — see governance).
- [ ] The standard task set in `50-govern/GOVERNANCE.md` has been reviewed
      by each function.

## After the paste — verification checklist

- [ ] `OB_Starter` and `OB_OnboardingTask` exist (Starter first).
- [ ] Create a test starter; create tasks against them — the Starter lookup
      offers the test row; TaskFunction/DueDate are required.
- [ ] Filter tasks by TaskFunction = IT: only IT tasks show (the per-team
      queue works).
- [ ] Any site Member can create and update rows.
- [ ] Delete the test tasks then the test starter.
- [ ] Even as an owner: changing a deployed column's type, choices or
      settings is refused (sealed) and List settings offers no "Delete
      this list"; a display-name rename is still possible — it is
      drift, reverted and reported at the next re-paste.

## Recommended views

| List | View | Filter / grouping |
|---|---|---|
| OnboardingTask | My function's queue | TaskFunction = (theirs), Status = Open, sort DueDate |
| OnboardingTask | Per starter | Filter by Starter — the manager's checklist |
| OnboardingTask | Overdue before start | Status = Open, DueDate < today |
| Starter | Starting soon | Status = Preparing, sort StartDate |

## Redeploying

Bump `schema_version`, rebuild, re-paste.
