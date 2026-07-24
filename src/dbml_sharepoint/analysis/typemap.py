# src/dbml_sharepoint/analysis/typemap.py
"""Map DBML column types to SharePoint field descriptors.

The output (SPField) is what the deploy.js template renders.
Field type kinds map to SP REST FieldTypeKind values:
  Text=2, Note=3, DateTime=4, Choice=6, Lookup=7, Boolean=8,
  Number=9, URL=11, User=20.
"""

from dataclasses import dataclass
from typing import Any, Literal

from dbml_sharepoint.model.parser import Column

type FieldKind = Literal[
    "Skip", "Text", "Note", "DateTime", "Choice", "Lookup",
    "Boolean", "Number", "URL", "User", "Calculated",
]

# DBML type -> SP.FieldCalculated OutputType (SP.FieldType: Text=2,
# DateTime=4, Number=9). Date output accepts SP's default DateFormat
# (DateOnly).
# The formula itself is NOT in DBML; it lives in the mapping's
# `calculated_formulas` section and is joined in at jsgen time.
CALCULATED_OUTPUT_TYPES: dict[str, int] = {
    "calculated_text": 2,
    "calculated_number": 9,
    "calculated_date": 4,
}


@dataclass(frozen=True)
class SPField:
    name: str
    kind: FieldKind
    field_type_kind: int | None
    required: bool
    unique: bool
    default: str | int | bool | None
    description: str
    # Type-specific:
    choices_enum: str | None = None
    target_list: str | None = None
    date_only: bool = True
    rich_text: bool = False
    number_of_lines: int = 6
    max_length: int = 255
    selection_mode: int = 0
    # SP.FieldUrl exposes the writable DisplayFormat property. Value 0 means
    # hyperlink (1 means image); ``UrlFormat`` is not a FieldUrl property.
    display_format: int = 0
    output_type: int | None = None


def map_column(col: Column, enum_names: set[str]) -> SPField:
    if col.is_pk and col.is_auto_increment and col.type == "int":
        return SPField(
            name=col.name, kind="Skip", field_type_kind=None,
            required=False, unique=False, default=None, description="",
        )

    description = format_description(col.note)

    if col.type == "choice":
        raise ValueError(
            f"{col.name}: legacy 'choice' type is not supported. "
            "Migrate to a named DBML enum.",
        )

    if col.type in CALCULATED_OUTPUT_TYPES:
        # Calculated columns are read-only derivations: never required/unique,
        # never defaulted. SP recalculates on every item edit.
        return SPField(
            name=col.name, kind="Calculated", field_type_kind=17,
            required=False, unique=False, default=None,
            description=description,
            output_type=CALCULATED_OUTPUT_TYPES[col.type],
        )

    if col.type in enum_names:
        return SPField(
            name=col.name, kind="Choice", field_type_kind=6,
            required=col.required, unique=False, default=col.default,
            description=description, choices_enum=col.type,
        )

    if col.ref is not None:
        return SPField(
            name=col.name, kind="Lookup", field_type_kind=7,
            required=col.required, unique=False, default=None,
            description=description, target_list=col.ref.target_table,
        )

    return _scalar(col, description)


def _scalar(col: Column, description: str) -> SPField:
    base: dict[str, Any] = dict(
        name=col.name, required=col.required, unique=col.unique,
        default=col.default, description=description,
    )
    match col.type:
        case "int":
            return SPField(**base, kind="Number", field_type_kind=9)
        case "number":
            return SPField(**base, kind="Number", field_type_kind=9)
        case "nvarchar":
            return SPField(**base, kind="Text", field_type_kind=2, max_length=255)
        case "longtext":
            return SPField(
                **base, kind="Note", field_type_kind=3,
                rich_text=False, number_of_lines=6,
            )
        case "richtext":
            return SPField(
                **base, kind="Note", field_type_kind=3,
                rich_text=True, number_of_lines=6,
            )
        case "person":
            return SPField(**base, kind="User", field_type_kind=20, selection_mode=0)
        case "date":
            return SPField(**base, kind="DateTime", field_type_kind=4, date_only=True)
        case "datetime":
            return SPField(**base, kind="DateTime", field_type_kind=4, date_only=False)
        case "boolean":
            return SPField(**base, kind="Boolean", field_type_kind=8)
        case "hyperlink":
            return SPField(**base, kind="URL", field_type_kind=11, display_format=0)
        case _:
            raise ValueError(
                f"{col.name}: unknown type {col.type!r}. "
                "Add it to typemap.py or declare it as an enum.",
            )


def format_description(note: str) -> str:
    if not note:
        return ""
    cleaned = " ".join(note.split())
    if len(cleaned) > 255:
        return cleaned[:252] + "..."
    return cleaned
