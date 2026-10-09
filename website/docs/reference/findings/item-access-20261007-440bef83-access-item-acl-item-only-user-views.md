---
title: "access.item-acl.item-only-user-views"
surface: access
scope: item-acl
question: item-only-user-views
probe_surface: access
state: open
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# access.item-acl.item-only-user-views

- Probe surface: access
- Run: item-access/20261007-440bef83
- Question: Can a user granted only on one file open the library's view and see that file?

## machine

- Outcome: `MANUAL`
- Evidence: effective on the library High=48 Low=134287360. By hand, as the test user: open the library's default view and say whether item-access-c3.txt is listed.

[All findings](../live-findings)
