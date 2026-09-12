---
title: "library.large-list.ui-group-by-indexed-column-folder-scoped"
surface: library
scope: large-list
question: ui-group-by-indexed-column-folder-scoped
probe_surface: library
state: needs-human
lanes: machine, visible
---

<!-- markdownlint-disable MD013 -->

# library.large-list.ui-group-by-indexed-column-folder-scoped

- Probe surface: library
- Run: library-large-list-modern-view/20260909-sandbox
- Question: Does scoping the grouped view inside a folder holding fewer than 5,000 files change the answer

## machine

- Outcome: `NOT REACHED`
- Evidence: STATE was 4, the unindexed witness. Paste again with STATE 5 if the filter pane opens.

## visible

- Recorded as: `ui-group-by-indexed-column-folder-scoped`
- Question: Does scoping the grouped view inside a folder holding fewer than 5,000 files change the answer?
- Verdict: `not_established`
- Confidence: 0.85
- Expected: The 'dbmlsp Probe PreIndex' library holds a folder of fewer than 5,000 files that a grouped view can be scoped into.
- Summary: The expected outcome needs a folder of fewer than 5,000 files inside 'dbmlsp Probe PreIndex' for a grouped view to be scoped into. The default view's first thirty rendered rows are all files with no folder row, but a page load renders only the first page of a 5,100-file library, so the absence of any folder is not established from what rendered.
- Observation: The visible content renders thirty rows, dbmlsp-pre-00001.txt through dbmlsp-pre-00030.txt, all files; no folder row and no folder name appears in the rendered content.
- Observation: The page renders a single page of rows out of a library the pre-capture REST read counted at 5,100 items, so the rendered content does not enumerate the library and cannot rule out a folder further down.
- Observation: The accessibility snapshot returned only the top-most modal layer, a 'Collect Files with Forms' teaching dialog, so it neither supports nor undercuts the reading of the grid; the rendered grid evidence for this check is the structured visible content.
- Observation: The screenshot was captured and hashed as sha256 6c3f510d18c2d6f1f391fcc3831b83afc50dc2f50288545b2139aa2bc4f46a3d, bracketed by matching pre- and post-capture page contexts on the requested URL. This reviewer reads text rather than images, so the screenshot is retained as a byte-exact record and carries no weight in this verdict.

![library.large-list.ui-group-by-indexed-column-folder-scoped](/findings/library/library-large-list-modern-view/20260909-sandbox/ui-group-by-indexed-column-folder-scoped.png)

[All findings](../live-findings)
