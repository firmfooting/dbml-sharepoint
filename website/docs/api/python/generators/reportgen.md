---
title: reportgen
sidebar_position: 24
---

# `dbml_sharepoint.generators.reportgen`

*Power Query / SQL reporting pack*

Report-query generator: Power Query (M) and T-SQL views from the schema.

The same DBML + mapping that provisions the lists also describes how to
report on them. This module emits:

- one Power Query (M) query per list, ``OData.Feed`` against the list's
  REST endpoint, with lookup and person columns expanded to a join key plus
  display column, and column types applied from the deployer's own typemap.
  ``build`` knows the site (``--site-url``) and bakes it into every query,
  so a shipped bundle has nothing to configure; the standalone ``report``
  command knows no site and falls back to a ``SiteUrl`` text parameter;
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
def generate_powerquery(schema: dbml_sharepoint.model.parser.Schema, bundle: dbml_sharepoint.model.mapping_types.MappingBundle, site_role: str, *, site_url: str | None = None) -> dict[str, str]
```

One M query per list for the site role: {filename: query text}.

Each query is self-contained, including its site-name lookup. That is
what makes a multi-site report possible: duplicate a query, point the
copy at another site's URL, and the name follows the rows. A shared
lookup query would bind to one URL and stamp that site's name onto
every copy.

``site_url``, when given, is bound as the first step of each query so
the pack works with nothing to configure. Omitted (the standalone
``report`` command has no site to name), the queries read a ``SiteUrl``
text parameter instead, and are otherwise identical.

### `generate_sql_views`

```python
def generate_sql_views(schema: dbml_sharepoint.model.parser.Schema, bundle: dbml_sharepoint.model.mapping_types.MappingBundle, site_role: str, *, site_url: str | None = None) -> str
```

A single SQLCMD script: typed view per list + _Enriched join views.

``site_url``, when known, is written into the ``:setvar SiteUrl`` line
so the script needs no editing; otherwise a placeholder is left there.

### `generate_reporting_md`

```python
def generate_reporting_md(schema: dbml_sharepoint.model.parser.Schema, bundle: dbml_sharepoint.model.mapping_types.MappingBundle, site_role: str, *, site_url: str | None = None) -> str
```

Usage instructions + the Power BI relationship table.

``site_url`` must be passed whenever the queries beside this guide were
built with it: the setup step it documents is the difference between
"create a parameter" and "there is nothing to create", and a guide that
is wrong about that costs the operator the whole first hour.

### `generate_data_dictionary`

```python
def generate_data_dictionary(schema: dbml_sharepoint.model.parser.Schema, bundle: dbml_sharepoint.model.mapping_types.MappingBundle, site_role: str, *, release: dbml_sharepoint.model.release.Release | None = None, generated_at: str = '', source_schema: str = '', source_mapping: str = '') -> str
```

Companion data dictionary: deployment/schema metadata + every list and
column as deployed, including choices, lookup targets, calculated
formulas, indexing, versioning and the query-layer helper columns.

### `generate_dictionary_powerquery`

```python
def generate_dictionary_powerquery(schema: dbml_sharepoint.model.parser.Schema, bundle: dbml_sharepoint.model.mapping_types.MappingBundle, site_role: str, *, release: dbml_sharepoint.model.release.Release | None = None, generated_at: str = '', source_schema: str = '', source_mapping: str = '', site_url: str | None = None) -> dict[str, str]
```

The data dictionary as report-loadable M queries, so any report can
surface it as a page: _DataDictionary (one row per column), _ModelInfo
(deployment/schema metadata as field/value rows) and _UserAddedColumns
(live drift audit, undeclared columns on the deployed lists).

``site_url`` reaches only _UserAddedColumns, the one query here that
talks to the site; it takes the same binding as the list queries, so a
bundle needs the ``SiteUrl`` parameter everywhere or nowhere.

### `generate_dictionary_sql`

```python
def generate_dictionary_sql(schema: dbml_sharepoint.model.parser.Schema, bundle: dbml_sharepoint.model.mapping_types.MappingBundle, site_role: str, *, release: dbml_sharepoint.model.release.Release | None = None, generated_at: str = '', source_schema: str = '', source_mapping: str = '') -> str
```

The data dictionary as SQL views built from embedded VALUES rows (no
landing table needed), so warehouse-driven reports can surface the same
dictionary page.

### `emit_reporting`

```python
def emit_reporting(out: pathlib.Path, schema: dbml_sharepoint.model.parser.Schema, bundle: dbml_sharepoint.model.mapping_types.MappingBundle, site_role: str, *, release: dbml_sharepoint.model.release.Release | None, generated_at: str, source_schema: str, source_mapping: str, site_url: str | None = None) -> list[str]
```

Write the reporting bundle under ``out/reporting/`` and return the
POSIX relpaths written (for checksums.txt).

Shared by the core and extension CLIs so the shipped reporting
artifact set cannot drift between them: per-list Power Query (M)
plus the dictionary/model/audit queries, the SQL views script,
the reporting guide and the data dictionary.

``site_url`` is the deployment target, which ``build`` always has.
Passing it bakes the site into every query, the SQL script and the
guide, so the pack loads with nothing configured. It is optional only
because ``report`` runs without a site at all.

