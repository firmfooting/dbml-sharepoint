---
title: "query.view-query.multichoice-membership-selects"
surface: query
scope: view-query
question: multichoice-membership-selects
probe_surface: field
state: open
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# query.view-query.multichoice-membership-selects

- Probe surface: field
- Run: multi-value/20260828-initial
- Question: the winning predicate survives being STORED as a view ViewQuery (manual: look)

## machine

- Recorded as: `C8`
- Outcome: `MANUAL`
- Evidence: stored Eq "View"; SharePoint read the query back as "\<Where>\<Eq>\<FieldRef Name=\\"Evt\\" />\<Value Type=\\"Text\\">View\</Value>\</Eq>\</Where>". OPEN \<sharepoint-url> dbmlsp multi value probe/Probe membership.aspx and confirm it lists exactly R1 and R2. A view that lists everything, or nothing, means the predicate does not survive storage and the condition grammar must refuse it however well GetItems behaved.

[All findings](../live-findings)
