# Deploying the improvement register (administrator)

Shared procedure: [`templates/README.md`](../../README.md) with
`<name> = improvement-register`. Template-specific notes below.

## Before you build

- [ ] `CI_` prefix free on the target site.
- [ ] `Source` enum matches the registers you actually run (complaints,
      incidents, audits, measures, the process inventory) — the feeding
      loops in governance depend on it.
- [ ] Someone owns the fortnightly triage (governance) — an untriaged
      suggestion box curdles fast.

## After the paste — verification checklist

- [ ] `CI_Improvement` exists; `MeasureBefore` is **required** (the
      form demands a baseline — that's deliberate).
- [ ] Raised `2026-07-01` + Adopted `2026-08-15` →
      **DaysIdeaToOutcome = 45**.
- [ ] Any Member can create and edit rows.
- [ ] Delete the test row.
- [ ] Even as an owner: changing a deployed column's type, choices or
      settings is refused (sealed) and List settings offers no "Delete
      this list"; a display-name rename is still possible — it is
      drift, reverted and reported at the next re-paste.

## Recommended views

| View | Filter / sort |
|---|---|
| Triage | Stage = Idea, oldest first |
| In flight | Stage = Planned/Testing, group by Owner |
| Adopted this quarter | Stage = Adopted, AdoptedDate in range, show Before/After |
| The learning shelf | Stage = Abandoned, newest first — failed tests are paid-for lessons |
| By source | Group by Source — which loops actually feed improvement |

## Redeploying

Bump `schema_version`, rebuild, re-paste.
