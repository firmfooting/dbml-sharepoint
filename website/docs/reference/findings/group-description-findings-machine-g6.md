---
title: "G6"
---

<!-- markdownlint-disable MD013 -->

# G6 (machine)

- Package: group-description-findings
- Question: What length comes back when 1000+ characters go out?
- Outcome: `FAIL`
- Evidence: the MERGE itself came back HTTP 500: \{"odata.error":\{"code":"-2146232832, Microsoft.SharePoint.SPException","message":\{"lang":"en-US","value":"The parameter Description cannot be null or bigger than 512 characters."}}}

[All findings](../live-findings)
