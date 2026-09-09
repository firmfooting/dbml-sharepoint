---
title: "library.view.group-by-multi-value-lookup"
surface: library
scope: view
question: group-by-multi-value-lookup
probe_surface: library
state: open
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# library.view.group-by-multi-value-lookup

- Probe surface: library
- Run: library-grouping/20260908-sandbox
- Question: Group-by on a multi-value lookup: one row per value held, or one group per set?

## machine

- Outcome: `NOT ESTABLISHED`
- Evidence: GroupMultiLookup: the two observations do not agree on either candidate: joined label(s) \[], expanded rows 4 against 4 file(s). collapsed HTTP 200 returned 5 row(s), labels \["",\[\{"lookupId":1,"lookupValue":"dbmlsp group target A","isSecretFieldValue":false}],\[\{"lookupId":1,"lookupValue":"dbmlsp group target A","isSecretFieldValue":false}],\[\{"lookupId":2,"lookupValue":"dbmlsp group target B","isSecretFieldValue":false}],\[\{"lookupId":2,"lookupValue":"dbmlsp group target , group-shaped keys \["GroupMultiLookup","GroupMultiLookup.urlencoded","GroupMultiLookup.singleurlencoded","GroupMultiLookup.COUNT.group","GroupMultiLookup.newgroup","GroupMultiLookup.groupindex"], first row \{"GroupMultiLookup":"","GroupMultiLookup.urlencoded":"%3B%23%3B%23","GroupMultiLookup.singleurlencoded":"","GroupMultiLookup.COUNT.group":"1","GroupMultiLookup.newgroup":"1","GroupMultiLookup.groupindex":"1\_","PreviewThumbnailsQualitySets":""}; expanded HTTP 200 returned 4 row(s) over 4 file(s), rows per file \{"dbmlsp-group-a-b.txt":1,"dbmlsp-group-b.txt":1,"dbmlsp-group-c.txt":1,"dbmlsp-group-none.txt":1}

[All findings](../live-findings)
