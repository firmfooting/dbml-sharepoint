---
title: "text.role-desc.length-ceiling"
surface: text
scope: role-desc
question: length-ceiling
probe_surface: text
state: failed
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# text.role-desc.length-ceiling

- Probe surface: text
- Run: role-definition/20260903-sandbox
- Question: What length comes back when 1000+ characters go out?

## machine

- Outcome: `FAIL`
- Evidence: HTTP 500: \{"odata.error":\{"code":"-2146232832, Microsoft.SharePoint.SPException","message":\{"lang":"en-US","value":"The parameter Description cannot be bigger than 512 characters."}}}

[All findings](../live-findings)
