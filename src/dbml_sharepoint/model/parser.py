# src/dbml_sharepoint/model/parser.py
"""DBML parser wrapper.

Wraps pydbml and post-processes its output into a stable in-memory schema
model the rest of the deployer works against.

The supported DBML subset is documented in
docs/design/requirements/dbml-sharepoint-requirements.md §5.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydbml import PyDBML
from pydbml.exceptions import (
    ColumnNotFoundError,
    DatabaseValidationError,
    TableNotFoundError,
)


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


@dataclass(frozen=True)
class TableIndex:
    """A table-level DBML index declaration.

    SharePoint accepts only bare single-column indexes. The DBML `name`,
    `unique`, `type`, `pk` and `note` settings are retained only so validation
    can reject them explicitly; declare uniqueness on the column with
    `[unique]` instead.
    """

    columns: tuple[str, ...]
    name: str | None = None
    unique: bool = False
    type: str | None = None
    pk: bool = False
    note: str = ""


@dataclass
class Table:
    """A DBML Table — name, columns, indexes, optional table-level note."""

    name: str
    columns: list[Column] = field(default_factory=list)
    indexes: list[TableIndex] = field(default_factory=list)
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


# pydbml reports schema-level problems in its own vocabulary, against its own
# model of the world: `Table public.Nope not present in the database`.
#
# `public` is a Postgres schema namespace that appears nowhere in DBML this
# tool accepts, in its documentation, or on a SharePoint site. `database` is
# not a word it uses either -- the target is a site, and the things being
# declared are lists. The person reading the sentence hand-edited a .dbml file
# and needs to know which declaration is wrong.
#
# Only these two shapes are translated, and only while they match exactly. An
# unrecognised parse error passes through untouched: pydbml's syntax errors
# already carry their own line and column and say nothing about `public`, and
# a message rendered into confident wrong prose is worse than a leaky one. If
# pydbml rewords these, the match fails and the real message survives.
_PYDBML_PHRASES: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"^Table public\.(?P<name>\S+) not present in the database\.?$"),
        "a ref targets table {name!r}, which this schema does not declare",
    ),
    (
        re.compile(r"^Table public\.(?P<name>\S+) is already in the database\.?$"),
        "table {name!r} is declared more than once",
    ),
)


def _translate(detail: str, source: str) -> str:
    """Re-word a recognised pydbml complaint, and cite a line if it can.

    The line is found by searching, because these messages carry no position
    at all -- pydbml raises them from its assembled model, after parsing, so
    there is nothing to hand through. Cited only when exactly one line
    mentions the name: two candidates and a guess would send somebody to the
    wrong declaration, which is worse than the honest silence of no line at
    all.
    """
    for pattern, template in _PYDBML_PHRASES:
        match = pattern.match(detail.strip())
        if match is None:
            continue
        name = match.group("name")
        reworded = template.format(name=name)
        hits = [
            number
            for number, line in enumerate(source.splitlines(), start=1)
            if re.search(rf"\b{re.escape(name)}\b", line)
        ]
        return f"{reworded} (line {hits[0]})" if len(hits) == 1 else reworded
    return detail


def parse_dbml(path: Path) -> Schema:
    """Parse a DBML file and return our in-memory model."""
    try:
        parsed = PyDBML(path)
    except (
        ColumnNotFoundError, TableNotFoundError, DatabaseValidationError,
    ) as exc:
        # These pydbml semantic errors do not inherit from ValueError or its
        # parser exception types, so normal CLI config-error handling would
        # otherwise miss them and print a traceback for a schema typo.
        #
        # pydbml's index message ends in an unformatted f-string fragment —
        # a literal `{self.name}` where the table name belongs. Drop the
        # whole clause, preposition included, rather than leaving the
        # sentence hanging on "not defined in.". The caller names the file,
        # which is the part an author actually needs. If pydbml ever fixes
        # the placeholder, this no longer matches and the real (better)
        # message passes through untouched.
        detail = str(exc).replace(' in table "{self.name}".', ".")
        raise ValueError(
            _translate(detail, path.read_text(encoding="utf-8")),
        ) from exc
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
        for raw_index in raw_table.indexes:
            table.indexes.append(TableIndex(
                columns=tuple(raw_index.subject_names),
                name=raw_index.name,
                unique=bool(raw_index.unique),
                type=raw_index.type,
                pk=bool(raw_index.pk),
                note=raw_index.note.text if raw_index.note else "",
            ))
        schema.tables.append(table)

    return schema


def _to_column(raw: Any) -> Column:
    """Convert a pydbml column object into our Column dataclass."""
    type_name = raw.type.name if hasattr(raw.type, "name") else str(raw.type)
    ref: Reference | None = None
    for raw_ref in getattr(raw, "get_refs", list)():
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
