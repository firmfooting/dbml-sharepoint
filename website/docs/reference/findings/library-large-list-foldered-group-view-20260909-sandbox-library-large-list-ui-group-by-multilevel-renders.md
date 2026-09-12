---
title: "library.large-list.ui-group-by-multilevel-renders"
surface: library
scope: large-list
question: ui-group-by-multilevel-renders
probe_surface: library
state: needs-human
lanes: machine, visible
---

<!-- markdownlint-disable MD013 -->

# library.large-list.ui-group-by-multilevel-renders

- Probe surface: library
- Run: library-large-list-foldered-group-view/20260909-sandbox
- Question: Does the modern page render three group levels on the small library

## machine

- Outcome: `NOT REACHED`
- Evidence: STATE was 0, the setup and REST leg. Each of these is read by opening a page and pasting again.

## visible

- Recorded as: `ui-group-by-multilevel-renders`
- Question: Does the modern page render three group levels on the small library?
- Verdict: `contradicted`
- Confidence: 0.95
- Expected: The 'MultiLevel By Three' view renders three levels of group headers on a 240-file library where nothing is near the threshold.
- Summary: The 'MultiLevel By Three' view did not render three group levels. On a 240-file library, nowhere near the threshold, the page rendered an alert reading 'Sorry, something went wrong', 'Unknown render failure.' and 'Cannot complete this action. Please try again.' with a correlation ID, and no group header or file row at all.
- Observation: The accessibility snapshot's main tabpanel holds a single alert node containing 'Sorry, something went wrong' and 'Unknown render failure. Cannot complete this action. Please try again. Correlation ID: 34a839a2-b061-8000-8d39-43dfe46754ad', with no grid, list, row or group node anywhere under main.
- Observation: The visible content carries the same alert text and contains no group header, no file name and no column header, so zero of the three expected group levels rendered.
- Observation: The library heading 'dbmlsp Probe MultiLevel' rendered and a pre-capture REST read counted 240 files, so this failure is not a threshold refusal; the rendered text never mentions the list view threshold.
- Observation: The screenshot was captured and hashed as sha256 84890cc4abb7f490330017e3035a62af69b56e56164eed8e7df59a50b482de3c, bracketed by matching pre- and post-capture page contexts on the requested URL. This reviewer reads text rather than images, so the screenshot is retained as a byte-exact record and carries no weight in this verdict.

![library.large-list.ui-group-by-multilevel-renders](/findings/library/library-large-list-foldered-group-view/20260909-sandbox/ui-group-by-multilevel-renders.png)

[All findings](../live-findings)
