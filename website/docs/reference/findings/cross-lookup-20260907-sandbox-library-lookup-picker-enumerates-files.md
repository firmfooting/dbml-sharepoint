---
title: "library.lookup.picker-enumerates-files"
surface: library
scope: lookup
question: picker-enumerates-files
probe_surface: library
state: open
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# library.lookup.picker-enumerates-files

- Probe surface: library
- Run: cross-lookup/20260907-sandbox
- Question: Does the picker for a list-to-library lookup offer files, or every item including folders?

## machine

- Outcome: `MANUAL`
- Evidence: OPEN \<sharepoint-url> and open the XListToLibTitle dropdown. The library holds exactly two rows, the file 'dbmlsp-xlookup.txt' and the folder 'dbmlsp-xlookup-folder'. Record how many entries the dropdown offers and what each one is labelled. Two entries means the picker enumerates ITEMS; one means it enumerates FILES; a blank label means the target rows have no Title, which is the library divergence this pair of rows exists to catch. The candidate set is rendered by the browser and is not exposed over REST, so this cannot be answered by a machine run.

[All findings](../live-findings)
