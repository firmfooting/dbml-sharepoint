# Deploying complaints & feedback (administrator)

Shared procedure: [`templates/README.md`](../../README.md) with
`<name> = complaints-feedback`. Template-specific notes below.

## Before you build

- [ ] `CF_` prefix free on the target site.
- [ ] Enums match your obligations (regulated sectors: your scheme may
      prescribe outcome categories — align now).
- [ ] You know who forms **CF Feedback Recorders** (front line) and
      **CF Feedback Handlers** — this template grants ordinary site Members
      nothing at all, so unlisted staff see nothing.

## After the paste — verification checklist

- [ ] `CF_Feedback` exists; custom level **CF Record Only** exists.
- [ ] Access split verified with three accounts:
      - ordinary Member: **cannot see the list at all**;
      - Recorder: can submit, cannot edit after saving;
      - Handler: can triage and edit.
- [ ] Received `2026-07-01`, Acknowledged `2026-07-03`, Closed `2026-07-15`
      → **DaysToAcknowledge = 2**, **DaysToClose = 14**.
- [ ] Populate both working groups; delete the test row (as Handler).
- [ ] Even as an owner: changing a deployed column's type, choices or
      settings is refused (sealed) and List settings offers no "Delete
      this list"; a display-name rename is still possible — it is
      drift, reverted and reported at the next re-paste.

## Recommended views

| View | Filter / sort |
|---|---|
| Triage | Status = Received, oldest first |
| Open by handler | Status ≠ Closed, group by Handler |
| Unacknowledged | AcknowledgedDate empty, Status ≠ Closed |
| Monthly report | Closed in month, group by FeedbackType, show both day-counts and Outcome |

## Redeploying

Bump `schema_version`, rebuild, re-paste. The Record Only level's
permissions are reconciled every run.
