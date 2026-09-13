---
title: rendered_columns
sidebar_position: 11
---

# `dbml_sharepoint.analysis.rendered_columns`

*which columns a provisioned list actually has*

Which columns a provisioned SharePoint list actually has.

Every check family reads `rendered_columns`, and so does `analysis/joins.py`
(which a generator may import, unlike `analysis/checks/`), so this is a shared
fact rather than a private helper of the orchestrator that happened to define
it first. The comment above `rendered = all_items_rendered(...)` in
`checks/_views.py` records what a second copy of the same three-term union
cost: a dropped term left the other spelling's callers unaffected and nothing
compared them.

Nothing here may import from `analysis/checks/`, which imports this, or from
`analysis/validator.py`, which imports `analysis/checks/`. An edge back would
move the cycle rather than close it.

### `SYSTEM_COLUMNS`

```python
SYSTEM_COLUMNS = frozenset({'Author', 'Created', 'Editor', 'ID', 'Modified'})
```

### `LIBRARY_COLUMNS`

```python
LIBRARY_COLUMNS = frozenset({'FileLeafRef'})
```

### `system_columns_for`

```python
def system_columns_for(kind: EntityKind) -> frozenset[str]
```

The system columns a container of this kind renders.

Kind-aware so a library's views and formatters may name FileLeafRef,
where it has been measured; a list keeps refusing it, unmeasured.

### `UNDEPLOYABLE_DECLARATION_COLUMNS`

```python
UNDEPLOYABLE_DECLARATION_COLUMNS = frozenset({'Author', 'Created', 'Editor', 'FileLeafRef', 'ID', 'Modified', 'Title'})
```

### `undeployable`

```python
def undeployable(context: str, column: str) -> str
```

The message for a declaration on a column the deploy never writes.

### `rendered_columns`

```python
def rendered_columns(table: dbml_sharepoint.model.parser.Table, cross_site_cols: set[str], projected_cols: set[str] | frozenset[str] = frozenset()) -> set[str]
```

Column names that will actually exist on the provisioned SP list:
auto-increment Id is skipped at render time, cross-site logical columns
expand to &lt;col>Abbreviation / &lt;col>SiteUrl and never exist themselves.
projected_cols are the lookup-projection columns the mapping declares
(read-only dependent Lookups); they exist on the list and are renderable,
but are not DBML columns.

