---
title: "library.large-list.control-missing-group-column-ungrouped"
surface: library
scope: large-list
question: control-missing-group-column-ungrouped
probe_surface: library
state: failed
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# library.large-list.control-missing-group-column-ungrouped

- Probe surface: library
- Run: library-large-list-calculated/20260908-sandbox
- Question: NEGATIVE CONTROL: a group-by naming a column the library does not hold comes back ignored

## machine

- Outcome: `CONTROL FAILED, METHOD VOID`
- Evidence: REFUSED (request rejected; read the body). collapsed HTTP 500 returned 0 row(s) against a RowLimit of 100, labels \[], grouping markers \[], first row null; expanded HTTP 500 returned 0 row(s); the same query with no \<GroupBy> returned HTTP 200 with 100 row(s); collapsed body \{"odata.error":\{"code":"-1, Microsoft.SharePoint.Client.UnknownError","message":\{"lang":"en-US","value":"Unknown Error"}}}. A group-by naming a column that does not exist did not come back as the flat query, so honoured and ignored are not separable on this run and every grouped row below says less than it appears to.

[All findings](../live-findings)
