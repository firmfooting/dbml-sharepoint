---
title: dictionary
sidebar_position: 32
---

# `dbml_sharepoint.analysis.reporting.dictionary`

*the data dictionary's rows as plain text, before escaping*

The data dictionary's rows, as plain text.

Every cell here is unescaped prose. The markdown page, the `_DataDictionary`
query and the `vw_<prefix>DataDictionary` view all read the same rows, and
each renderer applies its own escaping (`_md_cell`, `_m_string`,
`_sql_string`), so the dictionary cannot say one thing on the page and
another in the model.

The users dimension's column vocabulary lives here for the same reason: the
query that reads the list and the rows that describe it come from one
table.

### `USERS_COLUMNS`

```python
USERS_COLUMNS = (('Id', 'Int64.Type', 'Id'), ('Title', 'type text', 'Name'), ('EMail', 'type text', 'Email'), ('UserName', 'type text', 'Account'), ('Department', 'type text', 'Department'), ('JobTitle', 'type text',…
```

### `PRINCIPAL_KINDS`

```python
PRINCIPAL_KINDS = (('0x010A', 'Person'), ('0x010B', 'SharePoint group'), ('0x010C', 'Domain group'))
```

### `column_rows_for_table`

```python
def column_rows_for_table(table: dbml_sharepoint.model.parser.Table, bundle: dbml_sharepoint.model.mapping_types.MappingBundle, enum_names: set[str], enum_members: dict[str, list[str]], cross_site_keys: set[tuple[str, str]]) -> list[tuple[str, str, str, str, str, str, str, str, str, str]]
```

Plain-text dictionary rows for one table: (column, type, required,
unique, default, retired, superseded by, populated when, save rule,
description).

Retired columns are still listed, and the generated list queries still
select them: history is the entire point of retiring rather than
deleting.

### `metadata_rows`

```python
def metadata_rows(bundle: dbml_sharepoint.model.mapping_types.MappingBundle, site_role: str, list_count: int, release: dbml_sharepoint.model.release.Release | None, generated_at: str, source_schema: str, source_mapping: str) -> list[tuple[str, str]]
```

Deployment/schema model metadata as plain (field, value) rows,
shared by the data-dictionary.md header and the _ModelInfo report table.

### `dictionary_rows`

```python
def dictionary_rows(schema: dbml_sharepoint.model.parser.Schema, bundle: dbml_sharepoint.model.mapping_types.MappingBundle, site_role: str) -> list[tuple[str, str, str, str, str, str, str, str, str, str, str]]
```

(list, column, type, required, unique, default, retired, superseded
by, populated when, save rule, description) for every column in the site
role, in schema order.

### `users_dictionary_rows`

```python
def users_dictionary_rows() -> list[tuple[str, str, str, str, str, str, str, str, str, str]]
```

Dictionary rows for the `_Users` dimension, in its column order.

