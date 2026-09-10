---
title: report_sql
sidebar_position: 40
---

# `dbml_sharepoint.generators.report_sql`

*the T-SQL side of the reporting pack*

The T-SQL side of the reporting pack.

A single SQLCMD script of ``CREATE OR ALTER VIEW`` statements: a typed view
per list plus an ``_Enriched`` view joining each lookup to its display
column, for lists landed in a warehouse by any extract process, and the
dictionary, model-info and drift-audit views built from embedded VALUES
rows.

Everything here returns SQL text, and every string that reaches it goes
through :func:`_sql_string`. What the views CARRY is decided by
``analysis/reporting/plan.py``; this module only writes it down. Person
columns land differently per extract tool, so the views carry them as
display-name text, and no derived column reaches this side because a
row-level M expression has no SQL to translate to.

### `generate_sql_views`

```python
def generate_sql_views(schema: dbml_sharepoint.model.parser.Schema, bundle: dbml_sharepoint.model.mapping_types.MappingBundle, site_role: str, *, site_url: str | None = None, time_zone: str | None = None) -> str
```

A single SQLCMD script: typed view per list + _Enriched join views.

``site_url``, when known, is written into the ``:setvar SiteUrl`` line
so the script needs no editing; otherwise a placeholder is left there.
``time_zone`` is the site's zone the queries beside this were built
with; the plans are built with it so the two describe the same columns.

### `generate_dictionary_sql`

```python
def generate_dictionary_sql(schema: dbml_sharepoint.model.parser.Schema, bundle: dbml_sharepoint.model.mapping_types.MappingBundle, site_role: str, *, release: dbml_sharepoint.model.release.Release | None = None, generated_at: str = '', source_schema: str = '', source_mapping: str = '', time_zone: str | None = None) -> str
```

The data dictionary as SQL views built from embedded VALUES rows (no
landing table needed), so warehouse-driven reports can surface the same
dictionary page.

