---
title: "library.index.fixture-file-count"
surface: library
scope: index
question: fixture-file-count
probe_surface: library
state: open
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# library.index.fixture-file-count

- Probe surface: library
- Run: library-index-threshold/20260919-dd817683
- Question: The fixture library holds at least 5001 files

## machine

- Outcome: `SHORT`
- Evidence: 2000 file(s) uploaded this run (hit the per-run cap); the library now holds 2000 item(s) of the 5001 wanted. Re-paste with BUILD\_FIXTURE = true until this reads PASS. Nothing below this line was measured, because a query on a library that is not past the threshold answers a different question.

[All findings](../live-findings)
