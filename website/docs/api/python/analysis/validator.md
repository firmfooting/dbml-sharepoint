---
title: validator
sidebar_position: 5
---

# `dbml_sharepoint.analysis.validator`

*fail-closed build-time rules*

Validation rules for the parsed schema.

### `RESERVED_NAMES`

```python
RESERVED_NAMES = frozenset({'Attachments', 'Author', 'Created', 'Editor', 'Modified', '_UIVersion'})
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

### `VIEW_OPERATORS`

```python
VIEW_OPERATORS = frozenset({'eq', 'geq', 'gt', 'is_not_null', 'is_null', 'leq', 'lt', 'neq'})
```

### `formula_column_refs`

```python
def formula_column_refs(formula: str) -> frozenset[str]
```

Column names referenced as ``[Name]`` in a calculated formula.

String literals are stripped first so bracket text inside a quoted
constant is not misread as a reference. Shared with jsgen, which orders
Phase-1 field creation by these references.

### `MAX_CALCULATED_FORMULA`

```python
MAX_CALCULATED_FORMULA = 1024
```

### `MAX_INTERNAL_NAME`

```python
MAX_INTERNAL_NAME = 32
```

### `Finding`

```python
@dataclass
class Finding:
    severity: Severity
    message: str
```

Finding(severity: Severity, message: str)

### `validate`

```python
def validate(schema: dbml_sharepoint.model.parser.Schema) -> list[dbml_sharepoint.analysis.validator.Finding]
```

### `validate_against_mapping`

```python
def validate_against_mapping(schema: dbml_sharepoint.model.parser.Schema, bundle: dbml_sharepoint.model.mapping_loader.MappingBundle) -> list[dbml_sharepoint.analysis.validator.Finding]
```

### `validate_all`

```python
def validate_all(schema: dbml_sharepoint.model.parser.Schema, bundle: dbml_sharepoint.model.mapping_loader.MappingBundle, extension: dbml_sharepoint.extension.DeploymentExtension) -> list[dbml_sharepoint.analysis.validator.Finding]
```

Run every validation stage: core schema rules, mapping cross-checks,
the cross-site/extension contract, then the active extension's
project-specific rules.

