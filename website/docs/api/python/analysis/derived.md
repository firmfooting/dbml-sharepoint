---
title: derived
sidebar_position: 30
---

# `dbml_sharepoint.analysis.derived`

*derived reporting columns: what each contributes and reads*

Derived reporting columns: what each one contributes, and what it reads.

Reporting-only columns declared under `derived_columns`. Nothing here is
deployed: no SharePoint field is created, nothing is read back, and a list
carries no trace of one. They exist in the generated Power Query and nowhere
else.

SHARED because two sides need the same facts and must not drift.
`reporting/plan` resolves each entry into a step and `generators/report_m`
emits it; `checks/_derived` refuses a declaration that names a column the
query does not produce, reading `plan.report_column_names` for what it does
produce. `AGENTS.md` is explicit that such a fact lives in a shared module,
and that a generator must never import from `analysis/checks/`.

WHY THE REFERENCE CHECK IS THE RULE THAT MATTERS. A derived column names its
inputs in a string. Nothing downstream reads that string until Power BI does:
the build succeeds, the pack writes, the query text is well formed, and the
failure arrives at refresh as `The column 'X' of the table wasn't found`,
which takes every query behind it with it. Measured on the consumer's model:
release 3.1.0 renamed each list's Title, six derived lookups went on asking
for `Title`, and thirteen queries were blocked with nothing before Power BI
saying a word.

### `DERIVED_TYPES`

```python
DERIVED_TYPES = {'logical': 'type logical', 'text': 'type text', 'number': 'type number', 'Int64': 'Int64.Type', 'date': 'type date', 'datetime': 'type datetime', 'datetimezone': 'type datetimezone'}
```

### `DERIVED_AGGREGATES`

```python
DERIVED_AGGREGATES = frozenset({'count', 'max', 'min', 'names'})
```

### `DERIVED_REFERENCE`

```python
DERIVED_REFERENCE = re.compile('\\[([^\\[\\]]+)\\]')
```

### `derived_references`

```python
def derived_references(text: str) -> tuple[str, ...]
```

Every column an M fragment names, in order and without duplicates.

### `derived_output_names`

```python
def derived_output_names(entry: dbml_sharepoint.model.mapping_types.DerivedColumn) -> tuple[str, ...]
```

The columns one entry ADDS to the query.

A `replace` entry adds nothing: it overwrites a column that is already
there, which is why it is not a collision with itself.

### `target_entity`

```python
def target_entity(entry: dbml_sharepoint.model.mapping_types.DerivedColumn) -> str
```

The entity a `lookup` or a `count` reads. Empty for an `expr`.

### `is_users_source`

```python
def is_users_source(entry: dbml_sharepoint.model.mapping_types.DerivedColumn) -> bool
```

Whether a `lookup` reads the users dimension rather than a list.

`_Users` is the one source that is not an entity. A person column has no
DBML ref to derive keys from, but the pack already gives it a `... Key`
into `_Users` for exactly this join, so the shape is the same and only
where the two key names come from differs.

### `lookup_key_columns`

```python
def lookup_key_columns(entry: dbml_sharepoint.model.mapping_types.DerivedColumn, entity: str) -> tuple[str, str]
```

The (this side, other side) key columns one join matches on.

Derived from the schema's own ref rather than declared, so a key spelled
in a mapping cannot disagree with the key the query carries. A `lookup`
matches this list's foreign key against the TARGET's row key; a `count`
matches this list's row key against the CHILD's foreign key, which is the
same join read from the other end.

### `users_column_names`

```python
def users_column_names() -> frozenset[str]
```

The internal names a `lookup` into `_Users` may pick.

