---
title: dictionary
sidebar_position: 33
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

### `DictionaryRow`

One column's dictionary entry, as plain text.

THE row shape every dictionary renderer takes its order from. Ten cells
of one type, so a transposition of two was invisible to `mypy --strict`
and to every test, and would have shipped three internally consistent,
wrong artifacts with nothing in the build able to see it (#255). Built
by keyword at every site, so a swap is a type error now, and read by
name on the markdown page; the loadable tables iterate it in field
order and name their columns off `LOADABLE_COLUMNS`.

### `LOADABLE_COLUMNS`

```python
LOADABLE_COLUMNS = ('Column', 'Type', 'Required', 'Unique', 'Default', 'Retired', 'SupersededBy', 'PopulatedWhen', 'SaveRule', 'Description')
```

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
def column_rows_for_table(table: dbml_sharepoint.model.parser.Table, bundle: dbml_sharepoint.model.mapping_types.MappingBundle, enum_names: set[str], enum_members: dict[str, list[str]], cross_site_keys: set[tuple[str, str]]) -> list[dbml_sharepoint.analysis.reporting.dictionary.DictionaryRow]
```

Plain-text dictionary rows for one table.

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
def dictionary_rows(schema: dbml_sharepoint.model.parser.Schema, bundle: dbml_sharepoint.model.mapping_types.MappingBundle, site_role: str) -> list[tuple[str, dbml_sharepoint.analysis.reporting.dictionary.DictionaryRow]]
```

(list title, row) for every column in the site role, in schema
order, the users dimension's last.

### `users_dictionary_rows`

```python
def users_dictionary_rows() -> list[dbml_sharepoint.analysis.reporting.dictionary.DictionaryRow]
```

Dictionary rows for the `_Users` dimension, in its column order.

