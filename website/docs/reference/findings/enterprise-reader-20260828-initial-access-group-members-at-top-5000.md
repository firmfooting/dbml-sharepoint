---
title: "access.group.members-at-top-5000"
surface: access
scope: group
question: members-at-top-5000
probe_surface: access
state: open
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# access.group.members-at-top-5000

- Probe surface: access
- Run: enterprise-reader/20260828-initial
- Question: How many members does web/sitegroups(id)/users return at $top=5000, as the deploy reads it?

## machine

- Recorded as: `C1`
- Outcome: `NOT ESTABLISHED (prerequisite)`
- Evidence: GROUP\_NAME is still the placeholder. Set it to a site group, and see C2: only a group with MORE members than the server page size can answer C2 and C3.

[All findings](../live-findings)
