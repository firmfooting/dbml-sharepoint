---
title: "X1"
---

<!-- markdownlint-disable MD013 -->

# X1 (machine)

- Package: multi-value-findings
- Question: the severity formatter this repo generates, on an array (manual: look)
- Outcome: `MANUAL`
- Evidence: OPEN \<sharepoint-url> and look at the Evt column. Report FOUR things: (a) does R1 \{View} get a GREEN pill; (b) does R2 \{View,Edit} get any pill at all; (c) what TEXT does each cell show, whether both members, one member, or something like "View,Edit" run together; and (d) is the cell background PLAIN, or filled a flat grey. (d) separates the two ways this can fail and they need different answers: a plain cell means the formatter matched nothing and rendered nothing, while a grey fill means it matched a neutral default and rendered a wrong answer confidently, which is worse because it looks like a verdict. Anything other than a green pill on R1 means the existing severity machinery cannot serve a multi-value column, and the specification needs a refusal rather than array-aware behaviour.

[All findings](../live-findings)
