---
title: "library.large-list.ui-column-header-filter-past-threshold"
surface: library
scope: large-list
question: ui-column-header-filter-past-threshold
probe_surface: library
state: needs-human
lanes: machine, visible
---

<!-- markdownlint-disable MD013 -->

# library.large-list.ui-column-header-filter-past-threshold

- Probe surface: library
- Run: library-large-list-modern-view/20260909-sandbox
- Question: Does the column-header filter on PChoice offer values past 5000 items

## machine

- Outcome: `NOT REACHED`
- Evidence: STATE was 4, the unindexed witness. Paste again with STATE 5 if the filter pane opens.

## visible

- Recorded as: `ui-column-header-filter-past-threshold`
- Question: Does the column-header filter on PChoice offer values past 5,000 items?
- Verdict: `not_established`
- Confidence: 0.9
- Expected: Opening the PChoice column header menu on a library of 5,100 files lists the column's filter values rather than refusing with the list view threshold.
- Summary: The PChoice column header rendered on the grouped view, but a column-header filter menu only opens on a click and this capture is a page load, so no filter value list and no refusal ever entered the rendered evidence. Whether the menu offers values past 5,000 items is not established here.
- Observation: The visible content renders the PChoice column header alongside Name, Modified and Modified By on the 'UI By PChoice' view of the 5,100-file library, so the header the check targets exists.
- Observation: The visible content contains no filter menu, no list of filter values and no threshold wording, because the capture loaded the page and never opened the header menu; the question cannot be answered from a page load.
- Observation: The accessibility snapshot returned only the top-most modal layer, a 'Collect Files with Forms' teaching dialog, and contains no column-header menu either.
- Observation: The screenshot was captured and hashed as sha256 9b49edba8073f06ff075703822277bbfd206d9f65af05e9a2ea1d51e6451912f, bracketed by matching pre- and post-capture page contexts on the requested URL. This reviewer reads text rather than images, so the screenshot is retained as a byte-exact record and carries no weight in this verdict.

![library.large-list.ui-column-header-filter-past-threshold](/findings/library/library-large-list-modern-view/20260909-sandbox/ui-column-header-filter-past-threshold.png)

[All findings](../live-findings)
