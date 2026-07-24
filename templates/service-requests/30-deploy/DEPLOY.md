# Deploying service requests (administrator)

Shared procedure: [`templates/README.md`](../../README.md) with
`<name> = service-requests`. Template-specific notes below.

## Before you build

- [ ] `SR_` prefix free on the target site.
- [ ] `Category` values map 1:1 to teams that will actually work a queue —
      a category nobody owns is a black hole with a name.
- [ ] Each category's team knows the queue habit is coming (see 40-adopt).

## After the paste — verification checklist

- [ ] `SR_Request` exists; custom level **SR Submit Only** exists.
- [ ] As an ordinary Member: submit works, editing afterwards doesn't.
- [ ] As a Service Teams member: pick up the test request (AssignedTo,
      Status), complete it.
- [ ] Requested `2026-07-01` + Completed `2026-07-04` →
      **DaysToComplete = 3**.
- [ ] Populate **SR Service Teams**; delete the test row.
- [ ] Even as an owner: changing a deployed column's type, choices or
      settings is refused (sealed) and List settings offers no "Delete
      this list"; a display-name rename is still possible — it is
      drift, reverted and reported at the next re-paste.

## Recommended views — the queues ARE the product

| View | Filter / grouping |
|---|---|
| Facilities queue | Category = Facilities, Status ≠ Completed/Declined, Priority then oldest |
| IT queue | Category = IT, same |
| *(one per category)* | … |
| Waiting | Status = Waiting - parts or approval — reviewed weekly |
| My requests | RequestedBy = [Me] — requesters' tracking view |
| Turnaround report | Completed in month, group by Category, show DaysToComplete |

## Redeploying

Bump `schema_version`, rebuild, re-paste.
