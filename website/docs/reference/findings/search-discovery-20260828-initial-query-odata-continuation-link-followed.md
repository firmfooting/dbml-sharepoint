---
title: "query.odata.continuation-link-followed"
surface: query
scope: odata
question: continuation-link-followed
probe_surface: search
state: open
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# query.odata.continuation-link-followed

- Probe surface: search
- Run: search-discovery/20260828-initial
- Question: Does following that continuation link return a further page of DIFFERENT items?

## machine

- Recorded as: `S12`
- Outcome: `NOT ESTABLISHED (prerequisite)`
- Evidence: the fixture list "dbmlsp Probe Threshold" could not be read on this site: HTTP 404: \{"odata.error":\{"code":"-1, System.ArgumentException","message":\{"lang":"en-US","value":"List 'dbmlsp Probe Threshold' does not exist at site with URL '\<site>'."}}}. It may not exist here, it may have been renamed, or this caller may not be able to read it. PASTE THIS INTO THE SITE THAT HOLDS IT, or point PAGING\_FIXTURE\_LIST at another large list and say which. THIS IS NOT "paging does not work"; nothing was measured.

[All findings](../live-findings)
