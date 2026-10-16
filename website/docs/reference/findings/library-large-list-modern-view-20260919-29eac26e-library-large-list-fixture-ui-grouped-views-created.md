---
title: "library.large-list.fixture-ui-grouped-views-created"
surface: library
scope: large-list
question: fixture-ui-grouped-views-created
probe_surface: library
state: open
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# library.large-list.fixture-ui-grouped-views-created

- Probe surface: library
- Run: library-large-list-modern-view/20260919-29eac26e
- Question: Both grouped views exist and read back carrying a single-level \<GroupBy> on the column they name

## machine

- Outcome: `ABORTED`
- Evidence: ALLOW\_WRITES is false, so no view was created. The fixture rows above were still read. Set ALLOW\_WRITES to true and paste again.

[All findings](../live-findings)
