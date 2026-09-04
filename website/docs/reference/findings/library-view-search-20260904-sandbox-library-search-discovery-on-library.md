---
title: "library.search.discovery-on-library"
surface: library
scope: search
question: discovery-on-library
probe_surface: library
state: open
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# library.search.discovery-on-library

- Probe surface: library
- Run: library-view-search/20260904-sandbox
- Question: is a document library, and a file inside it, discoverable through the search index the way a generic list is

## machine

- Outcome: `NOT ESTABLISHED`
- Evidence: both search queries answered (title query '"dbmlsp Probe LibViewSearch"', file query 'dbmlspVSSeedA') but returned no row for the library or a fixture file. The fixture was created minutes ago and search indexing is asynchronous: this is consistent with crawl latency and establishes nothing about crawlability. Re-run tomorrow against the retained fixture before reading a zero-row result as a divergence.

[All findings](../live-findings)
