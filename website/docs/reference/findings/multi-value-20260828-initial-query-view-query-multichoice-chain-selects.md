---
title: "query.view-query.multichoice-chain-selects"
surface: query
scope: view-query
question: multichoice-chain-selects
probe_surface: field
state: open
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# query.view-query.multichoice-chain-selects

- Probe surface: field
- Run: multi-value/20260828-initial
- Question: a chained any\_of predicate survives being STORED as a view ViewQuery

## machine

- Recorded as: `C14`
- Outcome: `MANUAL`
- Evidence: sent "\<Or>\<Or>\<Eq>\<FieldRef Name=\\"Evt\\"/>\<Value Type=\\"Text\\">View\</Value>\</Eq>\<Eq>\<FieldRef Name=\\"Evt\\"/>\<Value Type=\\"Text\\">Delete\</Value>\</Eq>\</Or>\<Eq>\<FieldRef Name=\\"Evt\\"/>\<Value Type=\\"Text\\">PermissionChange\</Value>\</Eq>\</Or>" and got \["R1 \{View}","R2 \{View,Edit}"]; SharePoint stored "\<Where>\<Or>\<Or>\<Eq>\<FieldRef Name=\\"Evt\\" />\<Value Type=\\"Text\\">View\</Value>\</Eq>\<Eq>\<FieldRef Name=\\"Evt\\" />\<Value Type=\\"Text\\">Delete\</Value>\</Eq>\</Or>\<Eq>\<FieldRef Name=\\"Evt\\" />\<Value Type=\\"Text\\">PermissionChange\</Value>\</Eq>\</Or>\</Where>" which replays to \["R1 \{View}","R2 \{View,Edit}"]. OPEN \<sharepoint-url> dbmlsp multi value probe/Probe chained membership.aspx and capture the stored chained view. Confirm R1 \{View} and R2 \{View,Edit} are visible, while R3 \{Edit,Export} and R4 \{} are absent. Same rows are weaker than they look. The padding members Delete and PermissionChange are held by no row, so dropping either arm during storage leaves the result identical: this row cannot tell a surviving chain from a truncated one. It establishes only that the view stored and still answers. Nor does it speak to all\_of: only a nested Or was stored here. test/manual/caml-chain-depth-probe.js seeds one row per member so the COUNT is the measurement, and it is what actually settled this: no query-side ceiling to 40 disjuncts, and a filter editor that truncates at ten.

[All findings](../live-findings)
