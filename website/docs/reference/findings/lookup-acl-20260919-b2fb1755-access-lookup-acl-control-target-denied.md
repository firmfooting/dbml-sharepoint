---
title: "access.lookup-acl.control-target-denied"
surface: access
scope: lookup-acl
question: control-target-denied
probe_surface: access
state: open
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# access.lookup-acl.control-target-denied

- Probe surface: access
- Run: lookup-acl/20260919-b2fb1755
- Question: CONTROL: is the second account actually denied the TARGET list?

## machine

- Outcome: `NOT ESTABLISHED`
- Evidence: the target read failed with HTTP 404, which is not an access denial. A throttled or erroring request is not evidence that the ACL holds. Re-run.

[All findings](../live-findings)
