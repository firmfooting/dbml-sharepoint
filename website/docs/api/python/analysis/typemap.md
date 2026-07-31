---
title: typemap
sidebar_position: 7
---

# `dbml_sharepoint.analysis.typemap`

*DBML types to SharePoint field descriptors*

Map DBML column types to SharePoint field descriptors.

The output (SPField) is what the deploy.js template renders.
Field type kinds map to SP REST FieldTypeKind values:
  Text=2, Note=3, DateTime=4, Choice=6, Lookup=7, Boolean=8,
  Number=9, URL=11, User=20.

### `CALCULATED_OUTPUT_TYPES`

```python
CALCULATED_OUTPUT_TYPES = {'calculated_text': 2, 'calculated_number': 9, 'calculated_date': 4}
```

### `CALCULATED_TYPES`

```python
CALCULATED_TYPES = frozenset({'calculated_date', 'calculated_number', 'calculated_text'})
```

### `UNIQUE_SUPPORTED_SCALAR_TYPES`

```python
UNIQUE_SUPPORTED_SCALAR_TYPES = frozenset({'date', 'datetime', 'int', 'number', 'nvarchar', 'person'})
```

### `supports_unique`

```python
def supports_unique(col: dbml_sharepoint.model.parser.Column, enum_names: set[str]) -> bool
```

Whether this DBML column maps to a uniqueness-capable SP field.

### `SPField`

```python
@dataclass(frozen=True)
class SPField:
    name: str
    kind: FieldKind
    field_type_kind: int | None
    required: bool
    unique: bool
    default: str | int | bool | None
    description: str
    choices_enum: str | None = None
    target_list: str | None = None
    date_only: bool = True
    rich_text: bool = False
    number_of_lines: int = 6
    max_length: int = 255
    selection_mode: int = 0
    display_format: int = 0
    output_type: int | None = None
```

SPField(name: str, kind: FieldKind, field_type_kind: int | None, required: bool, unique: bool, default: str | int | bool | None, description: str, choices_enum: str | None = None, target_list: str | None = None, date_only: bool = True, rich_text: bool = False, number_of_lines: int = 6, max_length: int = 255, selection_mode: int = 0, display_format: int = 0, output_type: int | None = None)

### `map_column`

```python
def map_column(col: dbml_sharepoint.model.parser.Column, enum_names: set[str]) -> dbml_sharepoint.analysis.typemap.SPField
```

Map a DBML column to its SharePoint field descriptor.

The uniqueness gate runs after the type resolves, not before: an
unrecognised type is the more useful complaint, and checking `[unique]`
first answered `blob [unique]` with "unique is not supported for 'blob'
columns" — true, but it buries the actual mistake. Resolving first also
keeps the supported-type vocabulary in one place, the match statement
below, rather than in a second hand-maintained set beside it.

### `TODAY_SENTINEL`

```python
TODAY_SENTINEL = re.compile('^today(?:([+-])(\\d+))?$')
```

### `NOW_SENTINEL`

```python
NOW_SENTINEL = re.compile('^now$')
```

### `TOTAL_FUNCTIONS`

```python
TOTAL_FUNCTIONS = {'sum': 'SUM', 'count': 'COUNT', 'avg': 'AVG', 'min': 'MIN', 'max': 'MAX', 'stdev': 'STDEV', 'var': 'VAR'}
```

### `NUMERIC_ONLY_TOTALS`

```python
NUMERIC_ONLY_TOTALS = frozenset({'avg', 'max', 'min', 'stdev', 'sum', 'var'})
```

### `format_description`

```python
def format_description(note: str) -> str
```

### `UNSUPPORTED_INDEX_TYPES`

```python
UNSUPPORTED_INDEX_TYPES = {'longtext': 'Multiple lines of text (Note)', 'richtext': 'Multiple lines of text (Note)', 'hyperlink': 'Hyperlink'}
```

