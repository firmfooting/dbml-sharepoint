# src/dbml_sharepoint/parser.py
"""DBML parser wrapper.

Wraps pydbml and post-processes its output into a stable in-memory schema
model the rest of the deployer works against.

The supported DBML subset is documented in
docs/design/requirements/dbml-sharepoint-requirements.md §5.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydbml import PyDBML


@dataclass(frozen=True)
class Reference:
    """Foreign-key reference to another table's column."""

    target_table: str
    target_column: str


@dataclass
class Column:
    """A single column on a DBML Table."""

    name: str
    type: str
    required: bool = False
    unique: bool = False
    default: str | int | bool | None = None
    ref: Reference | None = None
    note: str = ""
    is_pk: bool = False
    is_auto_increment: bool = False


@dataclass
class Table:
    """A DBML Table — name, columns, optional table-level note."""

    name: str
    columns: list[Column] = field(default_factory=list)
    note: str = ""


@dataclass
class EnumDef:
    """A DBML Enum declaration with ordered members."""

    name: str
    members: list[str] = field(default_factory=list)


@dataclass
class Schema:
    """In-memory representation of a parsed DBML schema."""

    tables: list[Table] = field(default_factory=list)
    enums: list[EnumDef] = field(default_factory=list)
    project_note: str = ""


def parse_dbml(path: Path) -> Schema:
    """Parse a DBML file and return our in-memory model."""
    parsed = PyDBML(path)
    schema = Schema()

    if parsed.project and parsed.project.note:
        schema.project_note = parsed.project.note.text

    for raw_enum in parsed.enums:
        members = [_strip_quotes(item.name) for item in raw_enum.items]
        schema.enums.append(EnumDef(name=raw_enum.name, members=members))

    for raw_table in parsed.tables:
        table = Table(
            name=raw_table.name,
            note=raw_table.note.text if raw_table.note else "",
        )
        for raw_col in raw_table.columns:
            table.columns.append(_to_column(raw_col))
        schema.tables.append(table)

    return schema


def _to_column(raw: Any) -> Column:
    """Convert a pydbml column object into our Column dataclass."""
    type_name = raw.type.name if hasattr(raw.type, "name") else str(raw.type)
    ref: Reference | None = None
    for raw_ref in getattr(raw, "get_refs", lambda: [])():
        # pydbml exposes refs from the column side; first one wins for our subset.
        target = raw_ref.table2.name if raw_ref.col1[0] is raw else raw_ref.table1.name
        target_col = raw_ref.col2[0].name if raw_ref.col1[0] is raw else raw_ref.col1[0].name
        ref = Reference(target_table=target, target_column=target_col)
        break
    return Column(
        name=raw.name,
        type=type_name,
        required=getattr(raw, "not_null", False),
        unique=getattr(raw, "unique", False),
        default=raw.default if getattr(raw, "default", None) not in (None, "") else None,
        ref=ref,
        note=raw.note.text if raw.note else "",
        is_pk=getattr(raw, "pk", False),
        is_auto_increment=getattr(raw, "autoinc", False),
    )


def _strip_quotes(value: str) -> str:
    """Strip surrounding double-quotes from an enum member literal."""
    return value.strip('"')
