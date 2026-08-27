# src/dbml_sharepoint/extract/decode.py
"""A list's fields as a draft schema plus the mapping facts behind it.

This is the one module that decides what a SharePoint field BECOMES. It
reads `RawField` records and produces DBML types, enum declarations and
the mapping declarations the forward build understands, together with an
itemised record of everything it could not recover.

The recovery rule throughout: a declaration is emitted only when it can
be derived, and everything else is recorded as unrecovered rather than
guessed. `analysis/typemap.py` remains the authority on what a DBML type
means, so the tables here name its vocabulary rather than restating it.
"""

import re
from dataclasses import dataclass, field
from typing import Any

from dbml_sharepoint.analysis.column_refs import rewrite_formula_refs
from dbml_sharepoint.analysis.typemap import (
    CALCULATED_TYPES,
    KNOWN_SCALARS,
    MULTI_VALUE_SUFFIX,
    is_boolean,
)
from dbml_sharepoint.extract.field_xml import RawField, builtin_reason, is_builtin
from dbml_sharepoint.extract.inverse import (
    invert_column_formatting,
    invert_column_validation,
    invert_form_visibility,
)
from dbml_sharepoint.model.mapping_types import auto_display_name

#: SharePoint `Type` to a DBML scalar, for the types that carry no further
#: qualification. The qualified ones (Note, DateTime, Choice, Calculated,
#: Lookup, Number) are decided in `_column_type` because an attribute
#: changes the answer, and a second entry here would be a copy that can
#: disagree with the branch that actually runs.
_SIMPLE_TYPES = {
    "Text": "nvarchar",
    "Boolean": "boolean",
    "URL": "hyperlink",
    "User": "person",
}

#: SharePoint `ResultType` on a Calculated field to this codebase's
#: calculated type. Keyed on what the platform writes; the values are
#: `typemap.CALCULATED_TYPES` members and a test pins that.
_CALCULATED_RESULTS = {
    "Text": "calculated_text",
    "Number": "calculated_number",
    "DateTime": "calculated_date",
}

#: A DBML identifier this tool will emit without qualification. A field
#: whose internal name fails this still becomes a column, because dropping
#: one is worse than naming the limitation, but the deploy cannot recreate
#: the same internal name and the notes say so.
_PLAIN_IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9]*$")

#: SharePoint's escape for a character an internal name cannot hold, e.g.
#: `Risk_x0020_Owner` for a column created in the UI as "Risk Owner".
_ENCODED_CHAR = re.compile(r"_x([0-9a-fA-F]{4})_")

#: Word boundaries for deriving an enum name from a PascalCase column name.
#: The same two breaks `mapping_types.auto_display_name` uses, because the
#: two answer the same question about the same string and a third rule for
#: where a word ends is a rule that comes to disagree.
_SNAKE_BREAK = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")

#: Enum names that would collide with the type vocabulary. `choice` is the
#: retired type `typemap.is_legacy_choice` refuses, so an enum called that
#: would produce a schema the build rejects for a reason nothing explains.
_RESERVED_ENUM_NAMES = frozenset({*KNOWN_SCALARS, *CALCULATED_TYPES, "choice"})

#: Columns the deploy provisions itself, which must never be re-declared
#: even when a tenant has customised them past `is_builtin`'s tests.
_RESERVED_COLUMN_NAMES = frozenset({"Id", "ID"})


@dataclass(frozen=True)
class Unrecovered:
    """One thing the source did not carry, or this tool would not guess.

    `kind` groups the notes; `subject` is the entity or `Entity.Column` it
    belongs to. Both are plain strings so a caller can sort and group them
    without importing an enumeration that would have to be kept current.
    """

    kind: str
    subject: str
    detail: str


@dataclass(frozen=True)
class DecodedColumn:
    """One recovered column, as the DBML emitter needs it."""

    name: str
    dbml_type: str
    required: bool = False
    unique: bool = False
    default: str | bool | None = None
    note: str = ""
    indexed: bool = False
    #: Kept so the notes can quote the element for a column whose type or
    #: settings only partly survived.
    raw: RawField | None = field(default=None, repr=False)


@dataclass(frozen=True)
class DecodedEnum:
    name: str
    members: tuple[str, ...]


@dataclass
class DecodedEntity:
    """One list, decoded into the schema and mapping halves."""

    name: str
    list_title: str
    columns: list[DecodedColumn] = field(default_factory=list)
    indexes: list[str] = field(default_factory=list)
    #: {column: display title} for every column whose live title is not
    #: what `display_names: {mode: auto}` would produce.
    display_overrides: dict[str, str] = field(default_factory=dict)
    calculated_formulas: dict[str, str] = field(default_factory=dict)
    column_formatting: dict[str, dict[str, Any]] = field(default_factory=dict)
    form_visibility: dict[str, dict[str, Any]] = field(default_factory=dict)
    column_validation: dict[str, dict[str, Any]] = field(default_factory=dict)
    #: Formatters this tool could not express as a style spec, kept whole so
    #: the operator can paste them back rather than rebuild them.
    preserved_formatters: dict[str, str] = field(default_factory=dict)
    #: Built-ins skipped, paired with the test that fired.
    skipped: list[tuple[str, str]] = field(default_factory=list)
    note: str = ""


@dataclass
class Extraction:
    """Everything one run recovered, plus everything it did not."""

    entities: list[DecodedEntity] = field(default_factory=list)
    enums: list[DecodedEnum] = field(default_factory=list)
    unrecovered: list[Unrecovered] = field(default_factory=list)
    #: How the fields arrived, named for the notes. Interpolated into
    #: prose, so it reads as "Extracted from a live read of the site".
    source: str = ""
    #: What a read structurally could not carry, whatever the live list
    #: has. Distinct from `unrecovered`, which is what this particular
    #: list had and this tool could not read.
    absences: tuple[str, ...] = ()

    def enum_names(self) -> set[str]:
        return {enum.name for enum in self.enums}


class _EnumRegistry:
    """Names the enums a run needs, sharing one where the members match.

    Two columns offering identical ordered choices came from one enum in
    whatever schema built the list, so they are given one here. That is a
    real recovery rather than a tidy-up: it is the only evidence the field
    XML carries about which columns shared a vocabulary.
    """

    def __init__(self) -> None:
        self._by_members: dict[tuple[str, ...], str] = {}
        self._by_name: dict[str, tuple[str, ...]] = {}

    def resolve(self, raw: RawField, entity: str) -> str:
        members = raw.choices
        existing = self._by_members.get(members)
        if existing is not None:
            return existing
        name = self._mint(_snake(raw.internal_name), entity)
        self._by_members[members] = name
        self._by_name[name] = members
        return name

    def _mint(self, base: str, entity: str) -> str:
        if base not in self._by_name and base not in _RESERVED_ENUM_NAMES:
            return base
        qualified = f"{_snake(entity)}_{base}"
        if qualified not in self._by_name and qualified not in _RESERVED_ENUM_NAMES:
            return qualified
        suffix = 2
        while f"{base}_{suffix}" in self._by_name:
            suffix += 1
        return f"{base}_{suffix}"

    def declarations(self) -> list[DecodedEnum]:
        return [
            DecodedEnum(name=name, members=members)
            for name, members in self._by_name.items()
        ]


def _decode_escapes(name: str) -> str:
    """`Risk_x0020_Owner` back to `Risk Owner`."""
    return _ENCODED_CHAR.sub(lambda m: chr(int(m.group(1), 16)), name)


def _snake(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", _decode_escapes(name)).strip("_")
    return _SNAKE_BREAK.sub("_", cleaned).lower() or "enum"


def decode_list(
    raws: list[RawField],
    *,
    entity: str,
    list_title: str,
    enums: _EnumRegistry,
    unrecovered: list[Unrecovered],
    list_description: str = "",
) -> DecodedEntity:
    """Decode one list's fields into a schema entity and its mapping facts."""
    decoded = DecodedEntity(name=entity, list_title=list_title, note=list_description)
    types: dict[str, str] = {}
    kept: list[RawField] = []

    for raw in raws:
        if is_builtin(raw):
            decoded.skipped.append((raw.internal_name, builtin_reason(raw)))
            continue
        if raw.internal_name in _RESERVED_COLUMN_NAMES:
            decoded.skipped.append((raw.internal_name, "the built-in item identifier"))
            continue
        kept.append(raw)

    # Types resolve first, in one pass, because the inverters below need to
    # know a referenced column's type before they can rebuild a condition
    # that mentions it, and a condition may name a column declared later.
    for raw in kept:
        col_type = _column_type(raw, entity, enums, unrecovered)
        if col_type is None:
            continue
        types[raw.internal_name] = col_type

    for raw in kept:
        col_type = types.get(raw.internal_name)
        if col_type is None:
            continue
        decoded.columns.append(_column(raw, col_type, entity, unrecovered))
        if raw.indexed:
            decoded.indexes.append(raw.internal_name)
        _recover_mapping(raw, decoded, types, entity, unrecovered)

    _recover_display_names(kept, decoded)
    _recover_renames(kept, decoded, unrecovered)
    return decoded


def _column_type(
    raw: RawField,
    entity: str,
    enums: _EnumRegistry,
    unrecovered: list[Unrecovered],
) -> str | None:
    """The DBML type for one field, or None when this tool will not name it.

    Returning None drops the column from the schema, which is why it is
    only reached for a field type the forward build has no way to create.
    Every such field is recorded, with its element, so the operator can see
    exactly what is missing rather than a shorter schema than they expected.

    The strings compared below are SharePoint's CAML field types, not DBML
    column types, so `typemap` owns none of them and there is no predicate
    to ask. `raw.sp_type` is read directly for the same reason: a local
    named `sp_type` reads to the column-type pins as a DBML type.
    """
    subject = f"{entity}.{raw.internal_name}"

    simple = _SIMPLE_TYPES.get(raw.sp_type)
    if simple is not None:
        if raw.sp_type == "User" and raw.user_selection_mode not in (
            None, "PeopleOnly",
        ):
            # The forward path always writes SelectionMode 0. Nothing in this
            # repository establishes which mode the other values are, so the
            # column is typed and the difference is reported.
            unrecovered.append(Unrecovered(
                "user-selection-mode", subject,
                f"UserSelectionMode is {raw.user_selection_mode!r}; `person` "
                "deploys as people-only, so re-check this column after build.",
            ))
        return simple

    if raw.sp_type == "Note":
        return "richtext" if raw.rich_text else "longtext"

    if raw.sp_type == "DateTime":
        return "date" if raw.date_only else "datetime"

    if raw.sp_type == "Number":
        # `int` and `number` both deploy as SP Number with the same
        # FieldTypeKind (typemap `_scalar`), so the read cannot tell them
        # apart. `number` is the wider of the two and is chosen for that.
        unrecovered.append(Unrecovered(
            "number-precision", subject,
            "SharePoint stores `int` and `number` identically, so the "
            "original declaration cannot be told apart; emitted as `number`.",
        ))
        return "number"

    if raw.sp_type in ("Choice", "MultiChoice"):
        if not raw.choices:
            unrecovered.append(Unrecovered(
                "empty-choice", subject,
                "a Choice column with no <CHOICES>; no enum can be derived.",
            ))
            return None
        if raw.fill_in_choice:
            # The forward build deploys every Choice with FillInChoice false,
            # so a list that allows write-ins loses that on redeploy.
            unrecovered.append(Unrecovered(
                "fill-in-choice", subject,
                "FillInChoice is TRUE (users may type values outside the "
                "list); the deploy always writes FillInChoice false.",
            ))
        name = enums.resolve(raw, entity)
        multi = raw.sp_type == "MultiChoice"
        return f"{name}{MULTI_VALUE_SUFFIX}" if multi else name

    if raw.sp_type == "Calculated":
        calculated = _CALCULATED_RESULTS.get(raw.result_type or "")
        if calculated is None:
            unrecovered.append(Unrecovered(
                "calculated-result-type", subject,
                f"ResultType {raw.result_type!r} has no calculated type here "
                f"(known: {', '.join(sorted(_CALCULATED_RESULTS))}).",
            ))
            return None
        if not raw.formula:
            # The column is still emitted: dropping it would hide the fact
            # that the live list has one. `build` refuses it by name
            # (CALCULATED_COLUMN_HAS_NO_FORMULA), so the gap surfaces at the
            # next gate rather than at deploy time.
            unrecovered.append(Unrecovered(
                "calculated-formula-missing", subject,
                "a Calculated column whose element carries no <Formula>, so "
                "nothing was written to `calculated_formulas`. The build will "
                "refuse the column until you supply one.",
            ))
        return calculated

    if raw.sp_type == "Lookup":
        # A lookup's target is a list GUID in the XML. Resolving it needs the
        # site's other lists, which only the live path reads, and a `ref` to
        # the wrong table is worse than none.
        unrecovered.append(Unrecovered(
            "lookup-target", subject,
            f"a Lookup column pointing at list {raw.lookup_list or 'unknown'}; "
            "add the `ref` by hand once the target entity is in the schema.",
        ))
        return None

    unrecovered.append(Unrecovered(
        "unsupported-field-type", subject,
        f"SharePoint field type {raw.sp_type!r} has no DBML type here. "
        f"The element was: {raw.raw_xml}",
    ))
    return None


def _column(
    raw: RawField, col_type: str, entity: str, unrecovered: list[Unrecovered],
) -> DecodedColumn:
    subject = f"{entity}.{raw.internal_name}"
    if not _PLAIN_IDENTIFIER.match(raw.internal_name):
        unrecovered.append(Unrecovered(
            "internal-name", subject,
            f"internal name {raw.internal_name!r} is not a plain identifier, so "
            "a deploy from this schema creates a column with a DIFFERENT "
            "internal name. Rename the live column, or accept the new one.",
        ))
    default: str | bool | None = raw.default
    if isinstance(default, str) and is_boolean(col_type):
        default = default.strip() in ("1", "TRUE", "True", "true")
    if default is not None and col_type in CALCULATED_TYPES:
        # A calculated column cannot carry a default; typemap refuses one.
        unrecovered.append(Unrecovered(
            "calculated-default", subject,
            f"a default of {raw.default!r} on a calculated column, which the "
            "forward build does not carry.",
        ))
        default = None
    return DecodedColumn(
        name=raw.internal_name,
        dbml_type=col_type,
        required=raw.required and col_type not in CALCULATED_TYPES,
        unique=raw.unique,
        default=default,
        note=raw.description,
        indexed=raw.indexed,
        raw=raw,
    )


def _recover_mapping(
    raw: RawField,
    decoded: DecodedEntity,
    types: dict[str, str],
    entity: str,
    unrecovered: list[Unrecovered],
) -> None:
    """Recover the mapping declarations behind one field's artifacts."""
    subject = f"{entity}.{raw.internal_name}"

    if raw.formula:
        decoded.calculated_formulas[raw.internal_name] = _internal_formula(raw, types)

    if raw.custom_formatter:
        spec, _ = invert_column_formatting(raw.custom_formatter, subject)
        if spec is not None:
            decoded.column_formatting[raw.internal_name] = spec
        else:
            decoded.preserved_formatters[raw.internal_name] = raw.custom_formatter
            unrecovered.append(Unrecovered(
                "column-formatting", subject,
                "the column formatter is not one this tool's style vocabulary "
                "produces, so it is preserved verbatim beside the mapping "
                "rather than re-derived.",
            ))

    if raw.client_validation_formula:
        visibility = invert_form_visibility(
            raw.client_validation_formula, types, subject,
        )
        if visibility is not None:
            decoded.form_visibility[raw.internal_name] = visibility
        else:
            unrecovered.append(Unrecovered(
                "form-visibility", subject,
                f"form visibility formula {raw.client_validation_formula!r} is "
                "not one `form_visibility` can express; re-declare it by hand.",
            ))

    if raw.validation_formula:
        if raw.validation_message is None:
            unrecovered.append(Unrecovered(
                "column-validation", subject,
                f"column validation formula {raw.validation_formula!r} carries "
                "no validation message, and the message is the point of "
                "`column_validation`; re-declare the rule by hand with one.",
            ))
        else:
            validation = invert_column_validation(
                raw.validation_formula, raw.validation_message, types, subject,
            )
            if validation is not None:
                decoded.column_validation[raw.internal_name] = validation
            else:
                unrecovered.append(Unrecovered(
                    "column-validation", subject,
                    f"column validation formula {raw.validation_formula!r} is not "
                    "a single comparison, which is all `column_validation` "
                    "declares; re-declare it by hand.",
                ))


def _internal_formula(raw: RawField, types: dict[str, str]) -> str:
    """A stored `<Formula>` with its references back in internal names.

    SharePoint resolves calculated-formula references against DISPLAY names
    (proven live in `test/manual/calculated-choice-operand.js`), which is
    why the build rewrites them on the way out. The mapping's
    `calculated_formulas` are authored in internal names, so the same
    `column_refs.rewrite_formula_refs` runs backwards here, using the
    `<FieldRefs>` the element carries rather than a guess at how a title
    was spelled.
    """
    display_to_internal = {
        auto_display_name(name): name for name in types if name in raw.field_refs
    }
    return rewrite_formula_refs(raw.formula or "", display_to_internal)


def _recover_display_names(kept: list[RawField], decoded: DecodedEntity) -> None:
    """Record the display titles `display_names: {mode: auto}` would miss."""
    for raw in kept:
        if raw.display_name != auto_display_name(raw.internal_name):
            decoded.display_overrides[raw.internal_name] = raw.display_name


def _rename_key(name: str) -> str:
    """Whitespace- and case-insensitive form of a name, for drift checks.

    SharePoint's internal-name derivation drops a space here and escapes one
    there (`Due_x002f_reviewdate` for "Due/review date" but
    `Risk_x0020_Owner` for "Risk Owner"), so whitespace is not a signal that
    a name changed, and neither is case. What is left is the character
    sequence that must match for the internal name to have been derived from
    the current title rather than an older one.
    """
    return "".join(ch for ch in name.lower() if not ch.isspace())


def _recover_renames(
    kept: list[RawField],
    decoded: DecodedEntity,
    unrecovered: list[Unrecovered],
) -> None:
    """Flag columns whose internal name is a fossil of an earlier title.

    `_recover_display_names` records a title that `auto` would not derive
    from the internal name. This answers the separate, harder question: is
    the internal name itself a fossil of a DIFFERENT title than the one
    shown now? SharePoint never renames an internal name when the column is
    renamed, so a "yes" means every reference to the old internal name - a
    formula, a view, a formatter, a Power Automate flow - breaks on rebuild.
    """
    for raw in kept:
        old = _rename_key(_decode_escapes(raw.internal_name))
        current = _rename_key(raw.display_name)
        if old == current:
            continue
        unrecovered.append(Unrecovered(
            "renamed-column",
            f"{decoded.name}.{raw.internal_name}",
            (
                f"internal name decodes to {_decode_escapes(raw.internal_name)!r} "
                f"but the column is titled {raw.display_name!r}; it was renamed "
                "after creation, so references to the old internal name break "
                "on rebuild"
            ),
        ))


def new_enum_registry() -> _EnumRegistry:
    """A registry for one run. Enums are schema-global, so one is shared
    across every list an extraction covers."""
    return _EnumRegistry()
