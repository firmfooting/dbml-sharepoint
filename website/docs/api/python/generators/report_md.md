---
title: report_md
sidebar_position: 46
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
def generate_data_dictionary(schema: dbml_sharepoint.model.parser.Schema, bundle: dbml_sharepoint.model.mapping_types.MappingBundle, site_role: str, *, resolved: dbml_sharepoint.analysis.resolve.ResolvedMapping, release: dbml_sharepoint.model.release.Release | None = None, generated_at: str = '', source_schema: str = '', source_mapping: str = '', time_zone: str | None = None) -> str
```

Companion data dictionary: deployment/schema metadata + every list and
column as deployed, including choices, lookup targets, calculated
formulas, indexing, versioning and the query-layer helper columns.
``time_zone`` is the site's zone the pack was built with, named in the
`DateZoneResolved` row.

No `resolved.require_resolved()` call here, unlike `jsgen` and
`assessgen`, which do widen to the whole mapping and say why. This one
writes documentation and touches no site, so the reason to fail closed
across roles does not apply, and `report` runs no validation pass of its
own: it must still describe site role A correctly when an entity that
belongs to an unrelated site role B carries the mapping's only bad
`from_enum`. `require_folders` below is read only for entities
`tables_for_role` already scoped to THIS role, the same scope
`declared_folders` was called at before, so a reachable defect there
surfaces as `UnknownFolderEnumError` rather than a silent omission.
Named rather than a `KeyError` because `pipeline.execute_report` catches
`ValueError` to clear a previously generated pack, and a `KeyError`
walks through that handler and leaves the stale pack looking current.

