---
title: "access.group.members-next-link-second-page"
surface: access
scope: group
question: members-next-link-second-page
probe_surface: access
state: open
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# access.group.members-next-link-second-page

- Probe surface: access
- Run: enterprise-reader/20260828-initial
- Question: Does following d.\_\_next return a further page of DIFFERENT members?

## machine

- Recorded as: `C3`
- Outcome: `NOT ESTABLISHED (prerequisite)`
- Evidence: GROUP\_NAME is still the placeholder. Set it to a site group, and see C2: only a group with MORE members than the server page size can answer C2 and C3.

[All findings](../live-findings)
