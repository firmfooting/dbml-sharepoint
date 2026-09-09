---
title: "library.large-list.multilevel-group-by-field-order"
surface: library
scope: large-list
question: multilevel-group-by-field-order
probe_surface: library
state: void
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# library.large-list.multilevel-group-by-field-order

- Probe surface: library
- Run: library-large-list-multilevel-group-view/20260908-sandbox
- Question: Does the order of the three \<FieldRef> children change what a three-level group-by is given
- Voided by: library.large-list.control-missing-group-column-ungrouped

## machine

- Outcome: `NO ORDER ANSWERED DIFFERENTLY`
- Evidence: 3 order(s) of the same three columns, each sent collapsed. Unindexed: LVChoice > LVNumber > LVDate: HTTP 500 rejected, 0 row(s), dimensions \[] \{"odata.error":\{"code":"-2147467259, Microsoft.SharePoint.SPException","message":\{"lang":"en-US","value":"Cannot complete this action.\\n\\nPlease try again."}}}; LVDate > LVNumber > LVChoice: HTTP 500 rejected, 0 row(s), dimensions \[] \{"odata.error":\{"code":"-2147467259, Microsoft.SharePoint.SPException","message":\{"lang":"en-US","value":"Cannot complete this action.\\n\\nPlease try again."}}}; LVNumber > LVChoice > LVDate: HTTP 500 rejected, 0 row(s), dimensions \[] \{"odata.error":\{"code":"-2147467259, Microsoft.SharePoint.SPException","message":\{"lang":"en-US","value":"Cannot complete this action.\\n\\nPlease try again."}}}. Indexed: not taken. The indexed half was not reached, so this row is about the unindexed legs alone.. Every order was given the same class of answer, so nothing below turns on which order the primary question used, and a view that groups on these three columns cannot be rescued by reordering them.

[All findings](../live-findings)
