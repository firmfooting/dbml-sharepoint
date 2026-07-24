---
title: typemap
sidebar_position: 6
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

### `SPField`

```python
@dataclass
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

### `format_description`

```python
def format_description(note: str) -> str
```

