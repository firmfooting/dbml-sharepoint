---
title: column_refs
sidebar_position: 10
---

# `dbml_sharepoint.analysis.column_refs`

*column names written inside a formula or formatter*

Column names written inside a calculated formula or a formatter JSON.

Read by rule modules under `analysis/checks/` and by `generators/jsgen.py`,
which orders Phase-1 field creation by a formula's references, so it lives
outside both packages. It is not named
`references.py`, because a ref in this codebase is already a DBML foreign
key.

Nothing here may import from `analysis/checks/` or `analysis/validator.py`,
or the cycle this module exists to close would move rather than close.

### `FORMULA_COLUMN_REF`

```python
FORMULA_COLUMN_REF = re.compile('\\[([^\\[\\]]+)\\]')
```

### `formatter_field_refs`

```python
def formatter_field_refs(node: object) -> frozenset[str]
```

Every `[$Field]` reference in a formatter JSON structure, walking
nested dicts/lists and scanning every string value.

### `formula_column_refs`

```python
def formula_column_refs(formula: str) -> frozenset[str]
```

Column names referenced as ``[Name]`` in a calculated formula.

String literals are stripped first so bracket text inside a quoted
constant is not misread as a reference. Shared with jsgen, which orders
Phase-1 field creation by these references.

