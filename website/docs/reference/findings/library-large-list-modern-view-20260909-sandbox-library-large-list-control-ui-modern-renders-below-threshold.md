---
title: "library.large-list.control-ui-modern-renders-below-threshold"
surface: library
scope: large-list
question: control-ui-modern-renders-below-threshold
probe_surface: library
state: needs-human
lanes: machine, visible
---

<!-- markdownlint-disable MD013 -->

# library.large-list.control-ui-modern-renders-below-threshold

- Probe surface: library
- Run: library-large-list-modern-view/20260909-sandbox
- Question: CONTROL: does this browser render a modern document library page at all, on a library UNDER the threshold

## machine

- Outcome: `NOT REACHED`
- Evidence: STATE was 4, the unindexed witness. Paste again with STATE 5 if the filter pane opens.

## visible

- Recorded as: `control-ui-modern-renders-below-threshold`
- Question: CONTROL: does this browser render a modern document library page at all, on a library UNDER the threshold?
- Verdict: `not_established`
- Confidence: 0.9
- Expected: The modern document library page for 'Documents' renders file rows to this browser, so a blank grid past 5,000 items would mean the threshold rather than the browser.
- Summary: The modern 'Documents' library page rendered its chrome, command bar, view selector and column headers, but the library is empty, so not one file row rendered. The control asks for rendered file rows and the page cannot supply them, so this browser's ability to render rows is not established from this capture.
- Observation: The visible content records the Documents library page with its command bar, the 'All Documents' view selector and the Name, Modified and Modified By column headers, so the modern list page itself rendered.
- Observation: The visible content carries no file row and instead reads 'Your files will show up here' and 'Drag and drop files here to access them from any device.', so this control library holds no files to render.
- Observation: The accessibility snapshot returned only the top-most modal layer, a 'Collect Files with Forms' teaching dialog, so it neither supports nor undercuts the reading of the grid; the rendered grid evidence for this check is the structured visible content.
- Observation: The screenshot was captured and hashed as sha256 608b99a145e14e41540426549e49509abcfcc93c5be997b41df57b3fe662c072, bracketed by matching pre- and post-capture page contexts on the requested URL. This reviewer reads text rather than images, so the screenshot is retained as a byte-exact record and carries no weight in this verdict.

![library.large-list.control-ui-modern-renders-below-threshold](/findings/library/library-large-list-modern-view/20260909-sandbox/control-ui-modern-renders-below-threshold.png)

[All findings](../live-findings)
