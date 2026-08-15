---
title: validator
sidebar_position: 7
---

# `dbml_sharepoint.analysis.validator`

*fail-closed build-time rules*

Validation rules for the parsed schema.

### `RESERVED_NAMES`

```python
RESERVED_NAMES = frozenset({'Attachments', 'Author', 'Created', 'Editor', 'ID', 'Id', 'Modified', '_UIVersion'})
```

### `SYSTEM_COLUMNS`

```python
SYSTEM_COLUMNS = frozenset({'Author', 'Created', 'Editor', 'ID', 'Modified'})
```

### `KNOWN_SCALARS`

```python
KNOWN_SCALARS = frozenset({'boolean', 'date', 'datetime', 'hyperlink', 'int', 'longtext', 'number', 'nvarchar', 'person', 'richtext'})
```

### `CALCULATED_TYPES`

```python
CALCULATED_TYPES = frozenset({'calculated_date', 'calculated_number', 'calculated_text'})
```

### `FORMULA_COLUMN_REF`

```python
FORMULA_COLUMN_REF = re.compile('\\[([^\\[\\]]+)\\]')
```

### `formatter_field_refs`

```python
def formatter_field_refs(node: object) -> frozenset[str]
```

Every `[$Field]` reference in a formatter JSON structure — walks
nested dicts/lists and scans every string value.

### `formula_column_refs`

```python
def formula_column_refs(formula: str) -> frozenset[str]
```

Column names referenced as ``[Name]`` in a calculated formula.

String literals are stripped first so bracket text inside a quoted
constant is not misread as a reference. Shared with jsgen, which orders
Phase-1 field creation by these references.

### `validate`

```python
def validate(schema: dbml_sharepoint.model.parser.Schema) -> list[dbml_sharepoint.analysis.findings.Finding]
```

Core schema rules, judged without reference to any mapping.

Unknown column types, duplicate tables, enum members a column does not
have — everything decidable from the DBML alone.

This is one of three entry points and they partition the rules; none is a
superset of another except `validate_all`, which is the union and is what
the CLI runs. `test_the_entry_points_partition_their_rules` pins that.

**A test asserting "no findings" through only one of them is asserting
less than it looks.** `validate_against_mapping` reports nothing at all
for a schema whose column type is misspelled — that rule lives here — so
an `== []` against it passes on a schema the build would reject.

### `validate_against_mapping`

```python
def validate_against_mapping(schema: dbml_sharepoint.model.parser.Schema, bundle: dbml_sharepoint.model._mapping_types.MappingBundle) -> list[dbml_sharepoint.analysis.findings.Finding]
```

Cross-check the mapping against the schema.

Each family of rules lives in its own module under analysis.checks;
this walks them in declared order and concatenates what they report.
Order is part of the contract — see that package's docstring.

### `validate_all`

```python
def validate_all(schema: dbml_sharepoint.model.parser.Schema, bundle: dbml_sharepoint.model._mapping_types.MappingBundle, extension: dbml_sharepoint.extension.DeploymentExtension) -> list[dbml_sharepoint.analysis.findings.Finding]
```

Run every validation stage: core schema rules, mapping cross-checks,
the cross-site/extension contract, then the active extension's
project-specific rules.

