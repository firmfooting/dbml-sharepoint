---
title: "search.discovery.title-match-exactness"
surface: search
scope: discovery
question: title-match-exactness
probe_surface: search
state: open
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# search.discovery.title-match-exactness

- Probe surface: search
- Run: search-discovery/20260828-initial
- Question: Querying for a list title: EVERY title that comes back, not just the expected one.

## machine

- Recorded as: `S4`
- Outcome: `NOT ESTABLISHED (prerequisite)`
- Evidence: LIST\_TITLE is still the placeholder. Set it to a real list title on this tenant, ideally one that is a prefix of another list's title, which is the case that decides whether a title can be a key at all.

[All findings](../live-findings)
