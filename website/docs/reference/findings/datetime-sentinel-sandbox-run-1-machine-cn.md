---
title: "CN"
---

<!-- markdownlint-disable MD013 -->

# CN (machine)

- Package: datetime-sentinel-sandbox-run-1
- Question: NEGATIVE CONTROL: CAML containing a bogus \<Nowww/> is refused
- Outcome: `FAIL`
- Evidence: a query containing \<Nowww/> was ACCEPTED and returned 0 row(s). SharePoint is not validating this element, so C1-C5 prove nothing about \<Now/> being real

[All findings](../live-findings)
