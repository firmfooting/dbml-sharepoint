---
title: "library.large-list.ui-threshold-banner-text"
surface: library
scope: large-list
question: ui-threshold-banner-text
probe_surface: library
state: needs-human
lanes: machine, visible
---

<!-- markdownlint-disable MD013 -->

# library.large-list.ui-threshold-banner-text

- Probe surface: library
- Run: library-large-list-foldered-group-view/20260909-sandbox
- Question: What does the rendered threshold refusal actually say, where one appears

## machine

- Outcome: `NOT REACHED`
- Evidence: STATE was 0, the setup and REST leg. Each of these is read by opening a page and pasting again.

## visible

- Recorded as: `ui-threshold-banner-text`
- Question: What does the rendered threshold refusal actually say, where one appears?
- Verdict: `contradicted`
- Confidence: 0.85
- Expected: Where the root-scoped group-by on 'dbmlsp Probe Foldered' is refused by the list view threshold, the modern page renders a refusal quoting the threshold wording, so the rendered refusal can be recognised by its text.
- Summary: The root-scoped grouped view on 'dbmlsp Probe Foldered' rendered no threshold refusal at all. The page returned one group header, 'PChoice: Unassigned (3)', covering the three folders at the library root, and the rendered text carries no threshold wording, no refusal and no error alert, so this capture does not supply the rendered refusal text the check expects.
- Observation: The visible content renders exactly one group header, 'PChoice: Unassigned' with the count '(3)', and no file row; three is the number of folders at the library root.
- Observation: The visible content contains no 'threshold', no 'exceeds', no 'Sorry, something went wrong' and no error alert, so the view rendered successfully rather than refusing.
- Observation: The page renders the library heading 'dbmlsp Probe Foldered' with no folder breadcrumb beneath it, so this is the library root rather than a folder scope.
- Observation: The accessibility snapshot returned only the top-most modal layer, a 'Collect Files with Forms' teaching dialog, so it neither supports nor undercuts the reading of the grid; the rendered grid evidence for this check is the structured visible content.
- Observation: The screenshot was captured and hashed as sha256 c3e90d8ffeb0725af40943cd92c9d9b11ddfc0ef16d1285c43f55f42de117068, bracketed by matching pre- and post-capture page contexts on the requested URL. This reviewer reads text rather than images, so the screenshot is retained as a byte-exact record and carries no weight in this verdict.

![library.large-list.ui-threshold-banner-text](/findings/library/library-large-list-foldered-group-view/20260909-sandbox/ui-threshold-banner-text.png)

[All findings](../live-findings)
