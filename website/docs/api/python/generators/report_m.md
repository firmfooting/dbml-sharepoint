---
title: report_m
sidebar_position: 40
---

# `dbml_sharepoint.generators.report_m`

*the Power Query side of the reporting pack*

The Power Query side of the reporting pack.

One M query per list, ``OData.Feed`` against the list's REST endpoint, with
lookup and person columns expanded to a join key plus display column and
column types applied from the deployer's own typemap; the ``_Users``
dimension; and the three loadable tables (``_DataDictionary``,
``_ModelInfo`` and the ``_UserAddedColumns`` drift audit).

Everything here returns M text, and every string that reaches it goes
through :func:`_m_string`. What the queries CARRY is decided by
``analysis/reporting/plan.py``; this module only writes it down. ``build``
knows the site (``--site-url``) and bakes it into every query, so a shipped
bundle has nothing to configure; the standalone ``report`` command knows
no site and falls back to a ``SiteUrl`` text parameter.

### `generate_powerquery`

```python
def generate_powerquery(schema: dbml_sharepoint.model.parser.Schema, bundle: dbml_sharepoint.model.mapping_types.MappingBundle, site_role: str, *, site_url: str | None = None, time_zone: str | None = None) -> dict[str, str]
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

``time_zone`` is the site's IANA zone, which both commands supply: each
query then carries its transitions and the site-date helpers. See
`build_plans` for why it is optional here.

### `generate_dictionary_powerquery`

```python
def generate_dictionary_powerquery(schema: dbml_sharepoint.model.parser.Schema, bundle: dbml_sharepoint.model.mapping_types.MappingBundle, site_role: str, *, release: dbml_sharepoint.model.release.Release | None = None, generated_at: str = '', source_schema: str = '', source_mapping: str = '', site_url: str | None = None, time_zone: str | None = None) -> dict[str, str]
```

The data dictionary as report-loadable M queries, so any report can
surface it as a page: _DataDictionary (one row per column), _ModelInfo
(deployment/schema metadata as field/value rows) and _UserAddedColumns
(live drift audit, undeclared columns on the deployed lists).

``site_url`` reaches only _UserAddedColumns, the one query here that
talks to the site; it takes the same binding as the list queries, so a
bundle needs the ``SiteUrl`` parameter everywhere or nowhere.

