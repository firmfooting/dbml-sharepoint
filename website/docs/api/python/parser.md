---
title: parser
sidebar_position: 1
---

# `dbml_sharepoint.parser`

*Model — parse DBML into the in-memory schema*

DBML parser wrapper.

Wraps pydbml and post-processes its output into a stable in-memory schema
model the rest of the deployer works against.

The supported DBML subset is documented in
docs/design/requirements/dbml-sharepoint-requirements.md §5.

### `Reference`

```python
@dataclass
class Reference:
    target_table: str
    target_column: str
```

Foreign-key reference to another table's column.

### `Column`

```python
@dataclass
class Column:
    name: str
    type: str
    required: bool = False
    unique: bool = False
    default: str | int | bool | None = None
    ref: dbml_sharepoint.parser.Reference | None = None
    note: str = ''
    is_pk: bool = False
    is_auto_increment: bool = False
```

A single column on a DBML Table.

### `Table`

```python
@dataclass
class Table:
    name: str
    columns: list[dbml_sharepoint.parser.Column] = list()
    note: str = ''
```

A DBML Table — name, columns, optional table-level note.

### `EnumDef`

```python
@dataclass
class EnumDef:
    name: str
    members: list[str] = list()
```

A DBML Enum declaration with ordered members.

### `Schema`

```python
@dataclass
class Schema:
    tables: list[dbml_sharepoint.parser.Table] = list()
    enums: list[dbml_sharepoint.parser.EnumDef] = list()
    project_note: str = ''
```

In-memory representation of a parsed DBML schema.

### `parse_dbml`

```python
def parse_dbml(path: pathlib.Path) -> dbml_sharepoint.parser.Schema
```

Parse a DBML file and return our in-memory model.

