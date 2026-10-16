---
title: "access.item-acl.custom-level-user-grant"
surface: access
scope: item-acl
question: custom-level-user-grant
probe_surface: access
state: open
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# access.item-acl.custom-level-user-grant

- Probe surface: access
- Run: item-access/20261007-440bef83
- Question: Does a user bound to the custom no-delete level on one file edit it, see its versions and fail to delete it, while seeing nothing else?

## machine

- Outcome: `MANUAL`
- Evidence: break HTTP 200, grant HTTP 200 on item-access-c3.txt; break HTTP 200, grant HTTP 200 on item-access-c3-delete.txt; after 1 read(s), 381 ms item-access-c3.txt holds 10:Read, 11:dbmlsp ItemAccess No Delete, 12:Read, 13:dbmlsp ItemAccess No Delete, 3:Full Control, 4:Read, 5:Edit and item-access-c3-delete.txt holds 10:Read, 11:dbmlsp ItemAccess No Delete, 12:Read, 13:dbmlsp ItemAccess No Delete, 3:Full Control, 4:Read, 5:Edit; HasUniqueRoleAssignments read true and true; effective on item-access-c3.txt High=432 Low=134419047 (DeleteListItems false), on the library High=48 Low=134287360, on the web High=48 Low=134287360; the user's levels at the library Limited Access, at the web Limited Access. By hand, as the test user: on item-access-c3.txt an edit saved and the version history opened; on item-access-c3-delete.txt a delete tried.

[All findings](../live-findings)
