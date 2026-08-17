---
title: rendered_columns
sidebar_position: 8
---

# `dbml_sharepoint.analysis.rendered_columns`

*which columns a provisioned list actually has*

Which columns a provisioned SharePoint list actually has.

Seven modules read `rendered_columns`, and
`analysis/joins.py` (which a generator may import, unlike `analysis/checks/`)
is one of them, so this is a shared fact rather than a private helper of the
orchestrator that happened to define it first. `checks/_views.py:965-988`
records what a second copy of the same three-term union cost: a dropped term
left the other spelling's callers unaffected and nothing compared them.

Nothing here may import from `analysis/checks/` or `analysis/validator.py`.
Both import this, so an edge back would move the cycle rather than close it.

### `SYSTEM_COLUMNS`

```python
SYSTEM_COLUMNS = frozenset({'Author', 'Created', 'Editor', 'ID', 'Modified'})
```

### `UNDEPLOYABLE_DECLARATION_COLUMNS`

```python
UNDEPLOYABLE_DECLARATION_COLUMNS = frozenset({'Author', 'Created', 'Editor', 'ID', 'Modified', 'Title'})
```

### `undeployable`

```python
def undeployable(context: str, column: str) -> str
```

The message for a declaration on a column the deploy never writes.

### `rendered_columns`

```python
def rendered_columns(table: dbml_sharepoint.model.parser.Table, cross_site_cols: set[str]) -> set[str]
```

Column names that will actually exist on the provisioned SP list:
auto-increment Id is skipped at render time, cross-site logical columns
expand to &lt;col>Abbreviation / &lt;col>SiteUrl and never exist themselves.

