# Deploying routine checks (administrator)

Shared procedure: [`templates/README.md`](../../README.md) with
`<name> = routine-checks`. Template-specific notes below.

## Before you build

- [ ] `RC_` prefix free on the target site.
- [ ] The paper checklists being replaced are collected — each becomes a
      CheckPoint row, and the paper stops the day this goes live (parallel
      running means neither record is complete).
- [ ] Out-of-range escalations per check type agreed in
      `50-govern/GOVERNANCE.md` and mirrored into each checkpoint's
      Instructions.

## After the paste — verification checklist

- [ ] `RC_CheckPoint` and `RC_CheckEntry` exist (CheckPoint first).
- [ ] **Load the checkpoint catalogue** — every fridge, trolley, round
      and route, with range, frequency, owner and instructions.
- [ ] Record a test entry: the CheckPoint lookup offers the catalogue;
      CheckedAt takes date **and time**; Reading and Result required.
- [ ] Any Member can record entries.
- [ ] Bookmark/QR the entry form at each physical checkpoint (a QR to the
      list's New form taped where the paper sheet was is the adoption
      trick that makes this stick).
- [ ] Delete the test entry.
- [ ] Even as an owner: changing a deployed column's type, choices or
      settings is refused (sealed) and List settings offers no "Delete
      this list"; a display-name rename is still possible — it is
      drift, reverted and reported at the next re-paste.

## Recommended views

| List | View | Filter / sort |
|---|---|---|
| CheckEntry | Today | CheckedAt = today, group by CheckPoint — the completeness glance |
| CheckEntry | Out of range | Result ≠ In range, newest first — the review queue |
| CheckEntry | Per checkpoint | Filter by CheckPoint — the history an auditor reads |
| CheckPoint | The catalogue | Active = Yes, group by CheckType |

## Redeploying

Bump `schema_version`, rebuild, re-paste.
