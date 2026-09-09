---
title: "library.large-list.control-group-by-single-value-column"
surface: library
scope: large-list
question: control-group-by-single-value-column
probe_surface: library
state: failed
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# library.large-list.control-group-by-single-value-column

- Probe surface: library
- Run: library-large-list-calculated/20260908-sandbox
- Question: POSITIVE CONTROL: a group-by on LVChoice is honoured past 5,000 items

## machine

- Outcome: `CONTROL FAILED, METHOD VOID`
- Evidence: REFUSED (threshold). collapsed HTTP 500 returned 0 row(s) against a RowLimit of 100, labels \[], grouping markers \[], first row null; expanded HTTP 500 returned 0 row(s); the same query with no \<GroupBy> returned HTTP 200 with 100 row(s); collapsed body \{"odata.error":\{"code":"-2147024860, Microsoft.SharePoint.SPQueryThrottledException","message":\{"lang":"en-US","value":"The attempted operation is prohibited because it exceeds the list view threshold."}}}. The fixture gives LVChoice four values, \["Alpha","Beta","Gamma","Delta"], over 5500 file(s). A group-by is not honoured here on a plain single-value column, so nothing below can attribute an unhonoured group-by to LVCalc being calculated.

[All findings](../live-findings)
