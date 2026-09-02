---
title: "access.group.members-no-top-next-link"
surface: access
scope: group
question: members-no-top-next-link
probe_surface: access
state: open
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# access.group.members-no-top-next-link

- Probe surface: access
- Run: enterprise-reader/20260828-initial
- Question: With NO $top, does web/sitegroups(id)/users return a short page and a d.\_\_next?

## machine

- Recorded as: `C2`
- Outcome: `NOT ESTABLISHED (prerequisite)`
- Evidence: GROUP\_NAME is still the placeholder. Set it to a site group, and see C2: only a group with MORE members than the server page size can answer C2 and C3.

[All findings](../live-findings)
