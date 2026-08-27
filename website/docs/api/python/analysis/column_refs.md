---
title: column_refs
sidebar_position: 11
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

### `rewrite_formula_refs`

```python
def rewrite_formula_refs(formula: str, rename: dict[str, str]) -> str
```

Rewrite a calculated formula's ``[Name]`` references through `rename`.

SharePoint resolves calculated-formula column references against DISPLAY
names when the formula is written, so once fields are renamed a formula
authored with internal names would fail to create. Authors keep writing
internal names; the build translates on the way out, and the extractor
translates back on the way in. One function, because the two directions
have to agree about what a reference is and where a string literal
begins; two copies would be free to disagree in the one direction
nothing re-reads. String literals are data and are never rewritten.

