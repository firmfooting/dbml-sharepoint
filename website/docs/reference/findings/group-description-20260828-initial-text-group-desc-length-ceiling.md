---
title: "text.group-desc.length-ceiling"
surface: text
scope: group-desc
question: length-ceiling
probe_surface: text
state: failed
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# text.group-desc.length-ceiling

- Probe surface: text
- Run: group-description/20260828-initial
- Question: What length comes back when 1000+ characters go out?

## machine

- Recorded as: `G6`
- Outcome: `FAIL`
- Evidence: the MERGE itself came back HTTP 500: \{"odata.error":\{"code":"-2146232832, Microsoft.SharePoint.SPException","message":\{"lang":"en-US","value":"The parameter Description cannot be null or bigger than 512 characters."}}}

[All findings](../live-findings)
