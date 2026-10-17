---
title: "scale.index.caml-isnotnull-unindexed-datetime"
surface: scale
scope: index
question: caml-isnotnull-unindexed-datetime
probe_surface: scale
state: open
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# scale.index.caml-isnotnull-unindexed-datetime

- Probe surface: scale
- Run: threshold-index/20261017-6bdd7e60
- Question: CAML IsNotNull, UNINDEXED DateTime (is an index NECESSARY?)

## machine

- Outcome: `SHORT (50 of 60, HTTP 200), truncation or fixture fault; SEEDCK separates them`
- Evidence: \[6000 item(s), run 'join-created-modified'] CAML \<Where>\<IsNotNull>\<FieldRef Name='NotNullUni'/>\</IsNotNull>\</Where>, HTTP 200: SPAN: Row 000003 .. Row 004903. \{ "Row" : \[\{ "ContentTypeId": "0x0100316C6B20D307224CBD63EEAA3BB663D1", "Title": "Row 000003", "\_ModerationComments": "", "File\_x0020\_Type": "", "File\_x0020\_Type.mapapp": "", "HTML\_x0020\_File\_x0020\_Type.File\_x0020\_Type.mapcon": "", "HTML\_x0020\_File\_x0020\_Type.File\_x0020\_Type.mapico": "icgen.

[All findings](../live-findings)
