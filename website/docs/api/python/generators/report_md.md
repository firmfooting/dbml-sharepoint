---
title: report_md
sidebar_position: 42
---

# `dbml_sharepoint.generators.report_md`

*the reporting pack's guide and data dictionary pages*

The two markdown documents of the reporting pack.

``guide.md`` carries the usage instructions and the Power BI relationship
table derived from the DBML refs; ``data-dictionary.md`` carries the
deployment metadata and every list and column as deployed. Both return
markdown text, and every free-text cell that reaches a table goes through
:func:`_md_cell`. What the pages SAY about the queries is read off
``analysis/reporting/plan.py`` and ``analysis/reporting/dictionary.py``;
this module only writes it down.

Cross-site reference columns are extension-expanded at deploy time into
shapes the core cannot know; they are skipped by the queries and listed
in ``guide.md``.

### `generate_reporting_md`

```python
def generate_reporting_md(schema: dbml_sharepoint.model.parser.Schema, bundle: dbml_sharepoint.model.mapping_types.MappingBundle, site_role: str, *, site_url: str | None = None, time_zone: str | None = None) -> str
```

Usage instructions + the Power BI relationship table.

``site_url`` must be passed whenever the queries beside this guide were
built with it: the setup step it documents is the difference between
"create a parameter" and "there is nothing to create", and a guide that
is wrong about that costs the operator the whole first hour. The same
holds for ``time_zone``: the guide describes the transitions and helpers
the queries carry, and it can only do so for the zone they were built
with.

### `generate_data_dictionary`

```python
def generate_data_dictionary(schema: dbml_sharepoint.model.parser.Schema, bundle: dbml_sharepoint.model.mapping_types.MappingBundle, site_role: str, *, release: dbml_sharepoint.model.release.Release | None = None, generated_at: str = '', source_schema: str = '', source_mapping: str = '', time_zone: str | None = None) -> str
```

Companion data dictionary: deployment/schema metadata + every list and
column as deployed, including choices, lookup targets, calculated
formulas, indexing, versioning and the query-layer helper columns.
``time_zone`` is the site's zone the pack was built with, named in the
`DateZoneResolved` row.

