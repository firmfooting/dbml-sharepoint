# Deploying meeting actions (administrator)

Shared procedure: [`templates/README.md`](../../README.md) with
`<name> = meeting-actions`. Template-specific notes below.

## Before you build

- [ ] `MA_` prefix free on the target site.
- [ ] `MeetingType` choices match your forums.

## After the paste — verification checklist

- [ ] `MA_Meeting`, `MA_Decision`, `MA_ActionItem` exist (Meeting first).
- [ ] Create a test meeting; then a decision and an action against it —
      both Meeting lookups offer the test row.
- [ ] The action demands `AssignedTo` and `DueDate` (required).
- [ ] Any ordinary Member can create all three (Contribute).
- [ ] Delete the test rows (action/decision first, then the meeting).
- [ ] Even as an owner: changing a deployed column's type, choices or
      settings is refused (sealed) and List settings offers no "Delete
      this list"; a display-name rename is still possible — it is
      drift, reverted and reported at the next re-paste.

## Recommended views

| List | View | Filter / grouping |
|---|---|---|
| ActionItem | Open by person | Status = Open/In progress, group by AssignedTo |
| ActionItem | Overdue | Status = Open/In progress, DueDate < today |
| ActionItem | This meeting | Filter by Meeting — link it from the agenda |
| Decision | Decision log | Sorted newest first |

## Redeploying

Bump `schema_version`, rebuild, re-paste.
