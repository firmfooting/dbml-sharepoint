---
title: reportgen
sidebar_position: 19
---

# `dbml_sharepoint.generators.reportgen`

*Power Query / SQL reporting pack*

Report-query generator: Power Query (M) and T-SQL views from the schema.

The same DBML + mapping that provisions the lists also describes how to
report on them. This module emits:

- one Power Query (M) query per list — ``OData.Feed`` against the list's
  REST endpoint, parameterised by a ``SiteUrl`` text parameter, with lookup
  and person columns expanded to a join key plus display column, and column
  types applied from the deployer's own typemap;
- a single T-SQL script of ``CREATE OR ALTER VIEW`` statements (SQLCMD
  variables for the landing/report schemas): a typed view per list plus an
  ``_Enriched`` view joining each lookup to its display column, for lists
  landed in a warehouse by any extract process;
- guide.md with usage instructions and the Power BI relationship table
  derived from the DBML refs.

Cross-site reference columns are extension-expanded at deploy time into
shapes the core cannot know; they are skipped here and listed in
guide.md. Person columns land differently per extract tool, so the SQL
views carry them as display-name text while the M queries expand both the
site-user id and display name.

### `generate_powerquery`

```python
def generate_powerquery(schema: dbml_sharepoint.model.parser.Schema, bundle: dbml_sharepoint.model._mapping_types.MappingBundle, site_role: str) -> dict[str, str]
```

One M query per list for the site role: {filename: query text}.

Each query is self-contained, including its site-name lookup. That is
what makes a multi-site report possible: duplicate a query, point the
copy at another site's URL, and the name follows the rows. A shared
lookup query would bind to one URL and stamp that site's name onto
every copy.

### `generate_sql_views`

```python
def generate_sql_views(schema: dbml_sharepoint.model.parser.Schema, bundle: dbml_sharepoint.model._mapping_types.MappingBundle, site_role: str) -> str
```

A single SQLCMD script: typed view per list + _Enriched join views.

### `generate_reporting_md`

```python
def generate_reporting_md(schema: dbml_sharepoint.model.parser.Schema, bundle: dbml_sharepoint.model._mapping_types.MappingBundle, site_role: str) -> str
```

Usage instructions + the Power BI relationship table.

### `generate_data_dictionary`

```python
def generate_data_dictionary(schema: dbml_sharepoint.model.parser.Schema, bundle: dbml_sharepoint.model._mapping_types.MappingBundle, site_role: str, *, release: dbml_sharepoint.model.release.Release | None = None, generated_at: str = '', source_schema: str = '', source_mapping: str = '') -> str
```

Companion data dictionary: deployment/schema metadata + every list and
column as deployed, including choices, lookup targets, calculated
formulas, indexing, versioning and the query-layer helper columns.

### `generate_dictionary_powerquery`

```python
def generate_dictionary_powerquery(schema: dbml_sharepoint.model.parser.Schema, bundle: dbml_sharepoint.model._mapping_types.MappingBundle, site_role: str, *, release: dbml_sharepoint.model.release.Release | None = None, generated_at: str = '', source_schema: str = '', source_mapping: str = '') -> dict[str, str]
```

The data dictionary as report-loadable M queries, so any report can
surface it as a page: _DataDictionary (one row per column), _ModelInfo
(deployment/schema metadata as field/value rows) and _UserAddedColumns
(live drift audit — undeclared columns on the deployed lists).

### `generate_dictionary_sql`

```python
def generate_dictionary_sql(schema: dbml_sharepoint.model.parser.Schema, bundle: dbml_sharepoint.model._mapping_types.MappingBundle, site_role: str, *, release: dbml_sharepoint.model.release.Release | None = None, generated_at: str = '', source_schema: str = '', source_mapping: str = '') -> str
```

The data dictionary as SQL views built from embedded VALUES rows (no
landing table needed), so warehouse-driven reports can surface the same
dictionary page.

### `emit_reporting`

```python
def emit_reporting(out: pathlib.Path, schema: dbml_sharepoint.model.parser.Schema, bundle: dbml_sharepoint.model._mapping_types.MappingBundle, site_role: str, *, release: dbml_sharepoint.model.release.Release | None, generated_at: str, source_schema: str, source_mapping: str) -> list[str]
```

Write the reporting bundle under ``out/reporting/`` and return the
POSIX relpaths written (for checksums.txt).

Shared by the core and extension CLIs so the shipped reporting
artifact set cannot drift between them: per-list Power Query (M)
plus the dictionary/model/audit queries, the SQL views script,
the reporting guide and the data dictionary.

