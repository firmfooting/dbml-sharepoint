# src/dbml_sharepoint/analysis/typemap.py
"""Map DBML column types to SharePoint field descriptors.

The output (SPField) is what the deploy.js template renders. The kind-token to
SP REST `FieldTypeKind` pairing is `FIELD_TYPE_KIND_BY_KIND` below, the one
place the numbers are written, rather than a list in this docstring that
nothing could check and that had already lost Calculated and MultiChoice.
"""

import re
from collections.abc import Collection, Iterable
from dataclasses import dataclass
from difflib import get_close_matches
from typing import Any, Literal

from dbml_sharepoint.analysis.limits import (
    MAX_FIELD_DESCRIPTION,
    MAX_TEXT_FIELD_LENGTH,
)
from dbml_sharepoint.model.parser import Column

type FieldKind = Literal[
    "Skip", "Text", "Note", "DateTime", "Choice", "Lookup",
    "Boolean", "Number", "URL", "User", "Calculated", "MultiChoice",
    "LookupMulti",
]

#: THE pairing of this codebase's field-kind token to SharePoint's numeric
#: `FieldTypeKind`. Every `SPField` below takes its `field_type_kind` from
#: here, so the number and the name are written down together exactly once.
#:
#: `Skip` is absent deliberately: it is not a SharePoint field type but this
#: tool's marker for the auto-increment `Id` column, which is never created,
#: and its `field_type_kind` is `None`.
#:
#: WHY THIS IS A MAP AND NOT ELEVEN LITERALS. The same eleven pairs were
#: re-spelled by hand, as integers, inside a Jinja template
#: (`templates/deploy/_field_reconcile.js.j2`), where nothing at build time
#: could compare them to these. A missing entry there does not fail the build;
#: it throws in the operator's browser, mid-deploy, on a customer site. The
#: template now renders this map as context and `test_typemap.py` asserts the
#: rendered key set is exactly this vocabulary, so a twelfth field kind cannot
#: reach a deploy script without its TypeAsString.
FIELD_TYPE_KIND_BY_KIND: dict[FieldKind, int] = {
    "Text": 2,
    "Note": 3,
    "DateTime": 4,
    "Choice": 6,
    "Lookup": 7,
    "LookupMulti": 7,
    "Boolean": 8,
    "Number": 9,
    "URL": 11,
    "MultiChoice": 15,
    "Calculated": 17,
    "User": 20,
}

#: Kinds that share a `FieldTypeKind` with a single-value sibling, keyed by the
#: single-value kind.
#:
#: MEASURED, not assumed. A multi-value lookup reads back FieldTypeKind=7, the
#: same number a single-value Lookup reads back, entity type SP.FieldLookup,
#: and is told apart only by TypeAsString="LookupMulti" and
#: AllowMultipleValues=true (test/manual/multilookup-probe.js,
#: `field.multilookup.create-readback-type`, 2026-09-02). So the kind number
#: does NOT determine the kind token, and every derivation below that inverts
#: the map has to say which arity it means.
MULTI_ARITY_KIND: dict[FieldKind, FieldKind] = {"Lookup": "LookupMulti"}

#: The inverse of the above: the single-value spelling of a multi-value kind.
SINGLE_ARITY_KIND: dict[FieldKind, FieldKind] = {
    multi: single for single, multi in MULTI_ARITY_KIND.items()
}

#: The inverse. What SharePoint reports as `TypeAsString` on read-back is this
#: codebase's kind token for every kind it emits, verified on a live tenant
#: rather than transcribed from a page, which is what makes the deployer's
#: immutable-shape assertion trustworthy (a wrong string there fails a field
#: that is in fact correct). 15/MultiChoice was measured on 2026-08-10
#: alongside FieldTypeKind=15 and Choices as Collection(Edm.String).
#:
#: SINGLE-VALUE KINDS ONLY. A number that two kinds share cannot invert, and
#: the arity that resolves it is not a property of the number: the deployer
#: asks the DECLARATION (`AllowMultipleValues`) and picks from this map or
#: `MULTI_TYPE_AS_STRING_PAIRS` below.
FIELD_KIND_BY_TYPE_KIND: dict[int, FieldKind] = {
    kind_number: kind
    for kind, kind_number in FIELD_TYPE_KIND_BY_KIND.items()
    if kind not in SINGLE_ARITY_KIND
}

#: The same pairing shaped for a JavaScript `new Map([...])` constructor.
#:
#: A LIST OF PAIRS rather than the dict, because `tojson` on a dict with
#: integer keys emits `{"2": "Text"}` (JSON object keys are strings), and the
#: deployer looks a field's numeric `FieldTypeKind` up in that Map. A Map built
#: from string keys misses every lookup, silently, and the field it was
#: verifying is then reported as shape-mismatched. Pairs keep the key an
#: integer on both sides.
TYPE_AS_STRING_PAIRS: list[tuple[int, str]] = sorted(FIELD_KIND_BY_TYPE_KIND.items())

#: The multi-arity half of the same question, keyed by the same numbers. The
#: deployer consults this one when a declared field says AllowMultipleValues,
#: and throws a named error when a kind number has no multi spelling.
MULTI_TYPE_AS_STRING_PAIRS: list[tuple[int, str]] = sorted(
    (FIELD_TYPE_KIND_BY_KIND[multi], multi) for multi in SINGLE_ARITY_KIND
)

#: Every multi-arity spelling collapsed onto its single-value one, for the
#: deployer's immutable-shape assertion.
#:
#: TypeAsString is immutable in the sense that a Lookup can never become a
#: Text. It is NOT immutable across arity: `AllowMultipleValues` flips both
#: ways on an existing lookup, HTTP 204 in each direction, measured 2026-09-02
#: (`field.multilookup.allow-multiple-values-mutability`). Comparing the raw
#: string would abort a field the tenant is perfectly willing to change, so
#: the assertion compares base types and arity reconciles as an ordinary
#: property.
BASE_TYPE_AS_STRING_PAIRS: list[tuple[str, str]] = sorted(SINGLE_ARITY_KIND.items())

#: The SP.Field properties a declaration owns that are not on every subtype.
#: The deployer reads them back with `$select`, compares them and MERGEs the
#: drifted ones; a property missing from this list is written on create and
#: then never verified again.
#:
#: RENDERED, not typed out, for the reason `TYPE_AS_STRING_PAIRS` is. The same
#: ten names were spelled twice in two Jinja templates, once to select them
#: (`deploy/_shape_probes.js.j2`) and once to compare them
#: (`deploy/_field_reconcile.js.j2`), so a property added to the comparison and
#: not the probe compares a declared value against `undefined` and reports
#: permanent drift on a field that is correct.
#:
#: `AllowMultipleValues` is here rather than in the immutable set on purpose:
#: it flips both ways on an existing lookup, HTTP 204 in each direction,
#: measured 2026-09-02 (`field.multilookup.allow-multiple-values-mutability`).
#: It is an ordinary reconciled property.
DERIVED_FIELD_PROPERTIES: list[str] = [
    "MaxLength", "RichText", "NumberOfLines", "AppendOnly", "Choices",
    "FillInChoice", "DisplayFormat", "SelectionMode",
    "Formula", "OutputType", "AllowMultipleValues",
]

#: How the deployer validates each derived property's read-back value. The
#: default is "an integer", which is what the four format and length
#: properties are; everything else says so here.
DERIVED_FIELD_PROPERTY_KINDS: dict[str, str] = {
    "Choices": "strings",
    "RichText": "boolean",
    "AppendOnly": "boolean",
    "FillInChoice": "boolean",
    "AllowMultipleValues": "boolean",
    "Formula": "string",
}

# DBML type -> SP.FieldCalculated OutputType. OutputType is an SP.FieldType
# value, the same enumeration FieldTypeKind draws on, so it is spelled through
# FIELD_TYPE_KIND_BY_KIND rather than as three more integers. Date output
# accepts SP's default DateFormat (DateOnly).
# The formula itself is NOT in DBML; it lives in the mapping's
# `calculated_formulas` section and is joined in at jsgen time.
CALCULATED_OUTPUT_TYPES: dict[str, int] = {
    "calculated_text": FIELD_TYPE_KIND_BY_KIND["Text"],
    "calculated_number": FIELD_TYPE_KIND_BY_KIND["Number"],
    "calculated_date": FIELD_TYPE_KIND_BY_KIND["DateTime"],
}

# THE calculated type vocabulary. This map is where it belongs, because a
# calculated type that has no OutputType cannot be deployed at all, so
# adding one here is not optional, which is what makes the keys
# authoritative. Everything else derives; a second hand-written copy is a
# set that can silently disagree, leaving a new type uncovered by every
# check that reads the stale one while the suite stays green.
# test_validator.py asserts these three names appear together in this file
# and nowhere else in the package.
CALCULATED_TYPES = frozenset(CALCULATED_OUTPUT_TYPES)

# The same vocabulary spelled for a human to read, because prose enumerating
# a set is a copy of that set. The `formula_target_not_calculated` message and
# its catalogue entry both listed "calculated_text or calculated_number" and
# both omitted calculated_date, so the one rule that has to tell an author
# what IS allowed named a legal type as illegal, in the terminal and in
# `explain` alike, while `risk-register` shipped a calculated date the build
# accepted without complaint. Derived here so a fourth type reaches every
# sentence that lists them.
CALCULATED_TYPE_LIST = ", ".join(sorted(CALCULATED_TYPES))

# THE scalar vocabulary, for the same reason CALCULATED_TYPES lives here:
# `map_column` below is what actually has to recognise a type, so this is the
# one place a new scalar cannot be forgotten. It was declared in validator.py,
# which meant the check and the mapper each held their own idea of what is
# supported and nothing compared them.
KNOWN_SCALARS = frozenset({
    "int", "number", "nvarchar", "longtext", "richtext", "person", "date", "datetime",
    "boolean", "hyperlink",
})

# WHAT COUNTS AS A DATE, and WHAT COUNTS AS A NUMBER, each in one place, for
# the same reason TODAY_SENTINEL below is. Both sets were spelled out
# byte-identically in two modules apiece: `_DATE_TYPES` in `conditions.py` and
# `validator.py`, `_NUMBER_TYPES` in `conditions.py` and (as
# `_NUMERIC_FOR_TOTALS`) in `checks/_views.py`.
#
# A fourth date type added to one copy and not the other means the CAML
# renderer and the validator disagree about what a date column is: `today+30`
# renders on one path and is refused on the other, or worse, is accepted by
# the check and emitted as the literal string "today". `typemap.py:TODAY_
# SENTINEL` records that this exact problem was found and fixed for the
# sentinel ("Comments said they must agree; nothing checked it, so now there
# is one pattern and a test"), and the type sets it is matched against did not
# get the same treatment at the time.
#
# This module is the right home because its docstring already claims to be the
# answer to "what is this column type, in SharePoint terms", and because it is
# the module a new DBML type cannot be added without editing.
#
# The calculated members are IN. A `calculated_date` is a date for every
# purpose these sets serve (comparison rendering, `today` sentinel
# admission, view totals), and excluding them is what made the demo planner
# and the condition renderer disagree in the first place. Note that
# `generators/demogen.py` keeps its own, SMALLER date set on purpose: it
# seeds authored rows, and a calculated column cannot be written to.
DATE_TYPES = frozenset({"date", "datetime", "calculated_date"})
NUMBER_TYPES = frozenset({"int", "number", "calculated_number"})


# THE ARITY SUFFIX. DBML has no array type, so this is not a spelling this
# project chose from several available ones -- it is the only one there is.
# Measured against pydbml: `Events audit_event[]` parses and `Column.type`
# comes back as the literal string `'audit_event[]'`, while a column SETTING
# (`Events audit_event [multi]`) is a ParseSyntaxException inside pydbml,
# reported in pyparsing's own vocabulary before this tool ever sees the file.
# The settings grammar is a closed set and `multi` is not in it.
MULTI_VALUE_SUFFIX = "[]"

# THE ITEM WRITE SHAPE, measured as `field.multichoice.item-write-shape` (the
# row once called M3) by `test/manual/multi-value-probe.js` on run 3,
# 2026-08-17: a multi-value column takes
# `{"__metadata": {"type": "Collection(Edm.String)"}, "results": [..]}`.
# Learn's list-item REST page documents no multi-value example at all, so the
# probe tried four candidate shapes most-likely-first and recorded which one
# SharePoint took. It broke on the first success, which means the three others
# (a bare `{results: [..]}`, a bare array, and a `;#`-delimited string) are
# UNMEASURED rather than refused. Spelled once here so the emitter and every
# reader of a multi-value payload quote the same measured string.
MULTI_VALUE_METADATA_TYPE = "Collection(Edm.String)"

# THE ITEM WRITE SHAPE FOR A MULTI-VALUE LOOKUP, measured as
# `field.multilookup.item-write-shape` by `test/manual/multilookup-probe.js` on
# 2026-09-02: `{"<Name>Id": {"results": [id1, id2]}}` returned HTTP 201, and a
# bare array under the same key was refused HTTP 400. The `__metadata` wrapper
# is what the value READS BACK as under `$select=<Name>Id` in verbose
# (`field.multilookup.item-read-shape`), so it is quoted here for readers and
# emitted on the write for symmetry with the multi-choice shape above.
#
# NOTE THE KEY. A multi-value lookup is addressed as `<Name>Id`, not `<Name>`:
# the same `Id` suffix a single-value lookup takes. The probe's
# `name-not-id-alias` candidate is UNMEASURED (the run broke on the first
# success), so nothing here claims the bare name is refused.
MULTI_VALUE_LOOKUP_METADATA_TYPE = "Collection(Edm.Int32)"


def is_multi_value(col_type: str) -> bool:
    """Whether a declared DBML type holds many values rather than one.

    ONE PREDICATE, because arity is a property of the DECLARATION and every
    denylist in this codebase is keyed by type NAME. `UNSUPPORTED_INDEX_TYPES`
    and `JOIN_BEARING_TYPES` are dicts and frozensets of names; `audit_event[]`
    is not a key in either, and the key could not be added -- it would have to
    be minted per enum per schema. So a membership test against them looks
    like it covers a multi-value column and silently does not, which is the
    shape of failure this project exists to close.

    Callers ask this instead of adding a string entry. The suffix test is
    deliberately arity-only and says nothing about which SharePoint field the
    type becomes; `map_column` decides that. Two multi-value kinds resolve
    today, an enum (MultiChoice) and a `ref` (LookupMulti), so a caller that
    needs to know WHICH must ask `is_multi_value_lookup` as well. `person[]`
    is still an unknown type.
    """
    return col_type.endswith(MULTI_VALUE_SUFFIX)


def element_type(col_type: str) -> str:
    """What one member of `col_type` is declared as.

    A scalar is its own element type, so a caller can resolve a name without
    branching on arity first -- which is the point: a branch is a place the
    two arms come to disagree.
    """
    return col_type.removesuffix(MULTI_VALUE_SUFFIX)


def choice_enum_for(col_type: str, enum_names: Collection[str]) -> str | None:
    """The enum backing a Choice or MultiChoice column, whatever its arity.

    THE NAME DERIVATION, ASKED ONCE. Three call sites tested `col.type in
    enum_names` against a dict or set keyed by the bare enum name, so
    `audit_event[]` missed all three while each rule read as though it covered
    the column -- the failure `unsupported_index_reason` already records.

    There is no arity branch: `element_type` returns a scalar unchanged and its
    docstring says a branch is where the two arms come to disagree.

    This is not for the arity-sensitive guards. `supports_unique` and the multi-value
    default refusal answer differently for the two arities by design, and are
    deliberately not routed here.
    """
    bare = element_type(col_type)
    return bare if bare in enum_names else None


def is_multi_value_lookup(col: Column, enum_names: Collection[str]) -> bool:
    """Whether this column is a lookup that holds many target items.

    THE TWO MULTI-VALUE KINDS DIVERGE and a caller has to know which it has.
    They share arity mechanics (no default, no unique, no index, a collection
    write shape) and differ where the tenant differs: a MultiChoice is written
    under its own name and holds strings, a LookupMulti is written under
    `<Name>Id` and holds item ids, and only the lookup carries a join.

    ASKED IN `_resolve_column`'s OWN ORDER, which is why the enum question is
    here at all. The resolver decides Choice before it looks at `ref`, so
    `audit_event[] [ref: > X.Id]` is a MultiChoice and its `ref` is ignored; a
    predicate that only tested `col.ref is not None` would call the same column
    a lookup and send every downstream rule down the wrong arm.

    Nothing here tests the element type against `KNOWN_SCALARS`. The resolver
    does not either: `blob [ref: > X.Id]` maps to a Lookup and the validator is
    what reports the unknown type, so `blob[] [ref: > X.Id]` behaves the same
    way rather than acquiring a second, arity-only opinion.
    """
    return (
        is_multi_value(col.type)
        and col.ref is not None
        and choice_enum_for(col.type, enum_names) is None
    )

# THE type-identity questions, asked as questions rather than spelled out.
#
# Every one of these was a bare `== "boolean"` somewhere else -- eight sites
# across four modules, which is what #101 measured. A literal comparison is
# invisible to this module: rename a type or give it an alias and `map_column`
# is necessarily updated, because nothing deploys otherwise, while the
# comparison just stops matching. Nothing raises and no finding fires; a
# boolean column takes the non-boolean path and renders `<Value Type="Text">`,
# which SharePoint stores and answers with the wrong rows.
#
# So the name is written ONCE, here, and `_resolve_column` and `_scalar` below
# ask these too. A predicate the mapper does not itself consult is a second
# opinion rather than the one answer, and free to drift from it -- which is
# the bug, relocated.
#
# `str | None` because the demo checks and `demogen` hold
# `types_by_col.get(name)`. A column with no declared type is not a boolean,
# and making each caller spell `or ""` is four more chances to forget.
#
# NOT frozensets of aliases: DBML declares exactly these names today
# (`KNOWN_SCALARS` is the vocabulary) and a set of one, per type, would be
# scaffolding for an alias nobody has asked for. Widening one of these later
# means editing one function, which is the property #101 wanted.
#
# `test_no_module_outside_typemap_compares_a_column_type_to_a_literal` keeps
# the eight from coming back.


def is_boolean(column_type: str | None) -> bool:
    """Whether this DBML type is the Yes/No column (SP Boolean, kind 8)."""
    return column_type == "boolean"


def is_person(column_type: str | None) -> bool:
    """Whether this DBML type is the Person-or-Group column (SP User, kind 20)."""
    return column_type == "person"


def is_hyperlink(column_type: str | None) -> bool:
    """Whether this DBML type is the Hyperlink column (SP URL, kind 11).

    Worth asking rather than assuming: a URL column is a RECORD over REST
    (SP.FieldUrlValue), not a scalar, so every caller that gets this wrong
    writes a bare string and the value silently does not arrive.
    """
    return column_type == "hyperlink"


def is_legacy_choice(column_type: str | None) -> bool:
    """Whether this is the retired `choice` type, which has no mapping at all.

    Two places must agree and previously each held the word: `validate_column`
    reports it as `LEGACY_CHOICE_TYPE`, and `_resolve_column` raises on it --
    the path `report` takes, because `report` does not validate. One spelling
    kept them from diagnosing the same schema two different ways.
    """
    return column_type == "choice"


def describe_unknown_type(declared: str, *, enums: Iterable[str]) -> str:
    """Say what to do about a type this build does not recognise.

    Two callers, deliberately one sentence: `validate_column` reports this as
    a Finding, and `map_column` raises it -- which is the path `report`
    takes, because `report` does not validate. The same schema diagnosed two
    different ways is how somebody comes to believe the two commands
    disagree about their file.

    Suggesting is arithmetic over data already held. The supported set is a
    closed frozenset in this module and the enums come from the parsed
    schema, so nothing here is an assertion about SharePoint -- which is why
    this can be generous where the rest of the codebase must not be.

    Enums are in the candidate list because the commonest version of this
    mistake is not `decimal`, it is somebody misspelling the name of an enum
    they declared themselves twenty lines up.

    When there is no near miss the answer is the whole list. `decimal` is not
    a typo, it is SQL vocabulary arriving in a DBML file, and only seeing
    `number` in the supported set teaches that.
    """
    candidates = sorted({*KNOWN_SCALARS, *CALCULATED_TYPES, *enums})
    near = get_close_matches(declared, candidates, n=3, cutoff=0.6)
    if near:
        return f"Did you mean {', '.join(repr(c) for c in near)}?"
    return (
        f"Supported types: {', '.join(candidates)}. "
        f"Anything else must be a DBML enum, which becomes a Choice column."
    )

# Microsoft documents unique constraints for SINGLE-VALUE Text, Choice,
# Number, Date/Time, Lookup and Person columns, and lists "Choice
# (multi-valued)", "Lookup (multi-valued)" and "Person (multi-valued)" as
# types that cannot enforce them. Arity is therefore not expressible here --
# these are scalar type NAMES -- and is asked separately below.
UNIQUE_SUPPORTED_SCALAR_TYPES = frozenset({
    "nvarchar", "int", "number", "date", "datetime", "person",
})


def supports_unique(col: Column, enum_names: set[str]) -> bool:
    """Whether this DBML column maps to a uniqueness-capable SP field.

    ARITY IS ASKED FIRST, and it has to be. The `ref` arm short-circuits
    before anything looks at the type at all, so a multi-value column
    carrying a ref was declared uniqueness-capable outright; and the scalar
    arm returns the right answer for `audit_event[]` only because that string
    happens not to be a member of a frozenset of scalar names. Correct by
    accident is the state this predicate exists to end -- the accident holds
    only while no denylist key is ever an array form, which is not a property
    anything enforces.

    Measured on 2026-08-10: a POST setting EnforceUniqueValues on a
    MultiChoice field returned HTTP 500, "This column type is not supported
    for indexing". Refused loudly rather than accepted-and-ignored, so this
    turns a failed deploy into a failed build rather than covering a silence.
    https://support.microsoft.com/en-US/SharePoint/lists/data-and-lists/create-list-relationships-by-using-lookup-columns
    """
    if is_multi_value(col.type):
        return False
    return (
        col.ref is not None
        or col.type in enum_names
        or col.type in UNIQUE_SUPPORTED_SCALAR_TYPES
    )


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
    max_length: int = MAX_TEXT_FIELD_LENGTH
    selection_mode: int = 0
    # SP.FieldUrl exposes the writable DisplayFormat property. Value 0 means
    # hyperlink (1 means image); ``UrlFormat`` is not a FieldUrl property.
    display_format: int = 0
    output_type: int | None = None


def map_column(col: Column, enum_names: set[str]) -> SPField:
    """Map a DBML column to its SharePoint field descriptor.

    The uniqueness gate runs after the type resolves, not before: an
    unrecognised type is the more useful complaint, and checking `[unique]`
    first answered `blob [unique]` with "unique is not supported for 'blob'
    columns" (true, but it buries the actual mistake). Resolving first also
    keeps the supported-type vocabulary in one place, the match statement
    below, rather than in a second hand-maintained set beside it.
    """
    field = _resolve_column(col, enum_names)
    if col.unique and not supports_unique(col, enum_names):
        raise ValueError(
            f"{col.name}: [unique] is not supported for SharePoint "
            f"{col.type!r} columns.",
        )
    if col.default is not None and is_multi_value(col.type):
        # Gated here rather than dropped in the field body, for the reason
        # every other gate in this module is: a dropped default is the silent
        # kind of wrong. The build goes green, the deploy verifies clean, and
        # the column an author declared a default for simply has none.
        #
        # There is no honest coercion available. DBML carries ONE scalar and
        # the item write shape measured on 2026-08-10 is a collection --
        # `{"__metadata": {"type": "Collection(Edm.String)"}, "results": [..]}`
        # -- so a single declared member would have to be guessed into a
        # one-element set, and an empty one reads back as `null` rather than
        # `[]`. Neither is a thing DBML said.
        raise ValueError(
            f"{col.name}: default: is not supported on a multi-value column. "
            f"DBML carries one scalar and SharePoint's write shape for "
            f"{col.type!r} is a collection.",
        )
    return field


def _resolve_column(col: Column, enum_names: set[str]) -> SPField:
    if col.is_pk and col.is_auto_increment and col.type == "int":
        return SPField(
            name=col.name, kind="Skip", field_type_kind=None,
            required=False, unique=False, default=None, description="",
        )

    description = format_description(col.note)

    if is_legacy_choice(col.type):
        raise ValueError(
            f"{col.name}: legacy 'choice' type is not supported. "
            "Migrate to a named DBML enum.",
        )

    if col.type in CALCULATED_OUTPUT_TYPES:
        # Calculated columns are read-only derivations: never required/unique,
        # never defaulted. SP recalculates on every item edit.
        return SPField(
            name=col.name, kind="Calculated",
            field_type_kind=FIELD_TYPE_KIND_BY_KIND["Calculated"],
            required=False, unique=False, default=None,
            description=description,
            output_type=CALCULATED_OUTPUT_TYPES[col.type],
        )

    # The NAME is derived once, for both arities. The arms below still branch
    # on arity because they differ in `kind` and `field_type_kind`.
    choices_enum = choice_enum_for(col.type, enum_names)

    if choices_enum is not None and not is_multi_value(col.type):
        return SPField(
            name=col.name, kind="Choice",
            field_type_kind=FIELD_TYPE_KIND_BY_KIND["Choice"],
            required=col.required, unique=col.unique, default=col.default,
            description=description, choices_enum=choices_enum,
        )

    if choices_enum is not None:
        # `SP.FieldChoice` DERIVES from
        # `SP.FieldMultiChoice` -- `Choices` is a FieldMultiChoice property,
        # which is why the deployer's existing Choice machinery already
        # understands the only derived property this type adds.
        #
        # No new creation machinery, MEASURED rather than argued. On
        # 2026-08-10 a plain POST to /fields with
        # `__metadata: {type: 'SP.FieldMultiChoice'}`, FieldTypeKind 15 and
        # `Choices: {results: [...]}` returned HTTP 201, and the field read
        # back TypeAsString="MultiChoice", FieldTypeKind=15, Choices as
        # Collection(Edm.String). Lookup remains the one field type that
        # needs the AddField detour; this is not in that class.
        #
        # `choices_enum` is the ELEMENT type. `audit_event[]` is not an enum
        # any schema declares, so resolving the members means asking what one
        # member of the collection is.
        return SPField(
            name=col.name, kind="MultiChoice",
            field_type_kind=FIELD_TYPE_KIND_BY_KIND["MultiChoice"],
            required=col.required, unique=col.unique, default=col.default,
            description=description, choices_enum=choices_enum,
        )

    if col.ref is not None:
        # ARITY CHANGES THE KIND TOKEN BUT NOT THE NUMBER. A multi-value lookup
        # reads back FieldTypeKind=7, the same number as a single-value one,
        # with TypeAsString="LookupMulti" and AllowMultipleValues=true
        # (measured 2026-09-02, test/manual/multilookup-probe.js). Taking the
        # number from `FIELD_TYPE_KIND_BY_KIND[kind]` is therefore correct for
        # both arms and stays correct if the map is ever re-ordered.
        #
        # The CREATE ROUTE is what actually differs, and jsgen owns it:
        # AddField refuses `AllowMultipleValues` outright (HTTP 400, the
        # property does not exist on SP.FieldCreationInformation), so the
        # multi-value arm goes through createfieldasxml.
        kind: FieldKind = "LookupMulti" if is_multi_value(col.type) else "Lookup"
        return SPField(
            name=col.name, kind=kind,
            field_type_kind=FIELD_TYPE_KIND_BY_KIND[kind],
            required=col.required, unique=col.unique, default=None,
            description=description, target_list=col.ref.target_table,
        )

    return _scalar(col, description, enum_names)


def _scalar(col: Column, description: str, enum_names: set[str]) -> SPField:
    base: dict[str, Any] = dict(
        name=col.name, required=col.required, unique=col.unique,
        default=col.default, description=description,
    )
    # Hoisted out of the match below, and the three that follow it with it. A
    # `case` pattern spelled as a bare name CAPTURES rather than compares, and
    # a value pattern has to be dotted -- which a module cannot do to its own
    # constants. Leaving them in the match would mean the predicates named a
    # vocabulary the mapper did not read, so widening one would change what
    # `conditions.py` renders and not what gets provisioned. That divergence
    # is the bug #101 is about, so it is not worth reintroducing to keep one
    # match statement tidy.
    kinds = FIELD_TYPE_KIND_BY_KIND
    if is_boolean(col.type):
        return SPField(**base, kind="Boolean", field_type_kind=kinds["Boolean"])
    if is_person(col.type):
        return SPField(
            **base, kind="User", field_type_kind=kinds["User"], selection_mode=0,
        )
    if is_hyperlink(col.type):
        return SPField(
            **base, kind="URL", field_type_kind=kinds["URL"], display_format=0,
        )

    match col.type:
        case "int":
            return SPField(**base, kind="Number", field_type_kind=kinds["Number"])
        case "number":
            return SPField(**base, kind="Number", field_type_kind=kinds["Number"])
        case "nvarchar":
            return SPField(
                **base, kind="Text", field_type_kind=kinds["Text"],
                max_length=MAX_TEXT_FIELD_LENGTH,
            )
        case "longtext":
            return SPField(
                **base, kind="Note", field_type_kind=kinds["Note"],
                rich_text=False, number_of_lines=6,
            )
        case "richtext":
            return SPField(
                **base, kind="Note", field_type_kind=kinds["Note"],
                rich_text=True, number_of_lines=6,
            )
        case "date":
            return SPField(
                **base, kind="DateTime", field_type_kind=kinds["DateTime"],
                date_only=True,
            )
        case "datetime":
            return SPField(
                **base, kind="DateTime", field_type_kind=kinds["DateTime"],
                date_only=False,
            )
        case _:
            # `enum_names` is what this call was told the schema declares, so
            # the suggestion can name the user's own enums. It said "Add it
            # to typemap.py or declare it as an enum" -- half an instruction
            # to go and edit this repository, printed to a SharePoint admin
            # editing a .dbml file.
            raise ValueError(
                f"{col.name}: unknown type {col.type!r}. "
                + describe_unknown_type(col.type, enums=enum_names),
            )


# THE `today` SENTINEL, in one place. `today`, `today+30`, `today-7`.
#
# Three modules read this same authored value and each held its own copy:
# the validator gates what may be declared, the condition renderers decide
# what it becomes in CAML, and the demo planner decides what it becomes in
# a seeded row. A copy that drifts wider or narrower than another passes
# the build with zero findings and emits the literal string "today" into a
# script, the same shape of failure as two readers disagreeing about a
# hyperlink value. Comments said they must agree; nothing checked it, so
# now there is one pattern and a test.
TODAY_SENTINEL = re.compile(r"^today(?:([+-])(\d+))?$")

# The current-INSTANT sentinel, for a datetime column that must be compared
# to the moment rather than to the day.
#
# NO OFFSET FORM, deliberately, and that is not an oversight. `today+/-N` has
# a verified rendering on both targets; `now+/-N` does not. NOW()+1 in a
# validation formula and <Today OffsetDays> combined with IncludeTimeValue
# are each plausible and each unobserved, and this project's rule is that
# unverified is treated as unknown. Bare `now` is what the probe on
# 2026-07-29 actually established, so bare `now` is what exists. Since
# 2026-09-02 a validation comparison against `now` renders [Modified] rather
# than NOW() (analysis/save_rules.py), so the CAML half is the unobserved one.
NOW_SENTINEL = re.compile(r"^now$")

# Declared view aggregations: the authored name, and SharePoint's own token
# for it. The renderer owns the translation, exactly as it does for a sort
# direction (`desc` -> Ascending="FALSE").
#
# THESE TOKENS ARE AN ENUMERATION, NOT ENGLISH. They are transcribed from
# the FieldRef element (Query) reference, which lists exactly AVG, COUNT,
# MAX, MIN, SUM, STDEV and VAR and notes they are case-insensitive:
# https://learn.microsoft.com/sharepoint/dev/schema/fieldref-element-query
#
# The live classic renderer does not agree with "case-insensitive":
# `Type="Sum"` (capitalised) stores and round-trips byte-identically but
# renders `Count= undefined`, while `Type="SUM"` renders `Sum= 42`
# (measured 2026-08-27 by test/manual/view-aggregations-probe.js). Emit
# UPPERCASE, which this table already does.
#
# `avg` is the exception: the English word is "Average" and the token is "AVG".
# A non-member is ACCEPTED (SharePoint stores it and reads it back
# unchanged) and then fails the whole view with "Unknown render failure".
# Nothing in the build or the readback can see the difference; a person
# opening the view is the only witness. `SUM` hides this, being both the
# token and the word, so transcribe from the reference rather than typing
# what the function is called.
#
# The full enumeration is offered, STDEV and VAR included. Probes are for
# UNDOCUMENTED behaviour, which is where the silent failures live; a member
# of a published enumeration is documented, and withholding it buys nothing
# while costing an adopter something SharePoint plainly does.
TOTAL_FUNCTIONS: dict[str, str] = {
    "sum": "SUM",
    "count": "COUNT",
    "avg": "AVG",
    "min": "MIN",
    "max": "MAX",
    "stdev": "STDEV",
    "var": "VAR",
}

# `count` is excluded because it counts ROWS, not values, so it is legal on
# any column a view displays. Everything else needs something to compute.
NUMERIC_ONLY_TOTALS = frozenset(set(TOTAL_FUNCTIONS) - {"count"})


def format_description(note: str) -> str:
    if not note:
        return ""
    cleaned = " ".join(note.split())
    if len(cleaned) > MAX_FIELD_DESCRIPTION:
        return cleaned[: MAX_FIELD_DESCRIPTION - len("...")] + "..."
    return cleaned


# SharePoint refuses an index on these, whatever the schema asks for. Kept here
# rather than in one check because two now need it: _structure rejects a
# DECLARED index on them, and _views must not RECOMMEND one. A remedy that
# fails the build is worse than the warning it answers.
#
# Calculated columns belong to the same class and are not listed, because they
# are identified by CALCULATED_TYPES rather than by a single type name. A
# caller excluding unindexable columns has to consult both.
UNSUPPORTED_INDEX_TYPES = {
    "longtext": "Multiple lines of text (Note)",
    "richtext": "Multiple lines of text (Note)",
    "hyperlink": "Hyperlink",
}

# Microsoft lists "Choice (multi-valued)" among the column types an index
# cannot be added to, and a probe on 2026-08-10 measured the refusal rather
# than trusting it: a POST setting Indexed=true on a MultiChoice field was
# refused -- "This column type is not supported for indexing" -- and read back
# Indexed=false. Read WITH ITS CONTROL, which is what makes it trustworthy:
# the same run set Indexed=true on a single-value Choice in the same list and
# it stuck, so the refusal belongs to the field type and not to the probe.
#
# Loud, not silent, which is the good outcome -- unlike a calculated column,
# where SharePoint accepts Indexed=true and reads back false. The build-time
# refusal still belongs here so a deploy fails closed before it starts.
# https://support.microsoft.com/office/add-an-index-to-a-sharepoint-column-f3f00554-b7dc-44d1-a2ed-d477eac463b0
#
# SHAREPOINT'S OWN NAME for the type, which is why it is one public constant
# rather than a string typed into each message. Microsoft spells it this way
# in both lists an author will be sent to -- the column types an index cannot
# be added to, and the column types unique values cannot be enforced for -- so
# a message quoting it is quoting the page the reader will land on. The DBML
# spelling (`audit_event[]`) is the wrong thing to lead with in a refusal: it
# names the enum, and invites deleting the brackets, which changes what the
# column means rather than dropping the setting that is refused.
#
# ONE NAME PER MULTI-VALUE KIND, which is what the previous single constant
# said would have to happen the day a second multi-value type resolved: "the
# day one of them is added it has to be revisited HERE rather than at every
# call site". It has been.
#
# "Lookup (multi-valued)" is Microsoft's own spelling on both pages, alongside
# "Choice (multi-valued)", and the refusal was measured the same way: on
# 2026-09-02 a POST setting Indexed=true on a LookupMulti field was refused
# HTTP 500, "This column type is not supported for indexing", and read back
# Indexed=false, while the SAME RUN's control -- a single-value Lookup in the
# same list, targeting the same list -- took the index and kept it. So the
# refusal belongs to the multiplicity and not to lookups
# (test/manual/multilookup-probe.js, `field.multilookup.indexed-property` and
# `.control-single-value-indexed`).
MULTI_VALUE_SP_TYPE_NAMES: dict[FieldKind, str] = {
    "MultiChoice": "Choice (multi-valued)",
    "LookupMulti": "Lookup (multi-valued)",
}


def multi_value_sp_type_name(*, lookup: bool = False) -> str:
    """SharePoint's own name for the multi-value column type `lookup` selects.

    A FLAG RATHER THAN A `Column`, because the two callers that render this
    into a message hold different things: one has the parsed column, the other
    only a declared type string out of a `types_by_col` map. Both can answer
    "is this a lookup", and neither should be typing the string.
    """
    return MULTI_VALUE_SP_TYPE_NAMES["LookupMulti" if lookup else "MultiChoice"]


def unsupported_index_reason(col_type: str, *, lookup: bool = False) -> str | None:
    """The SharePoint type name that explains why `col_type` cannot be
    indexed, or None if it can.

    THE ACCESSOR EXISTS SO THE DENYLIST CAN BE ARITY-AWARE. Three call sites
    used to test `col.type in UNSUPPORTED_INDEX_TYPES` directly, and that dict
    is keyed by DBML type name -- so `audit_event[]` misses every one of them
    while the rule reads as though it covers the column. Two of the three
    produce a build error and the third decides whether to RECOMMEND an index,
    which on a multi-value column would prescribe a remedy the deploy cannot
    carry out.

    `lookup` only picks which name comes back, never whether one does: both
    multi-value kinds are refused an index, so a caller that cannot tell a
    lookup from an enum still gets the right verdict and a slightly wrong noun.

    Calculated columns are deliberately still not covered here: they are
    identified by CALCULATED_TYPES rather than by one type name, and a caller
    excluding unindexable columns has to consult both. That is a second
    predicate, not a second string.
    """
    if is_multi_value(col_type):
        return multi_value_sp_type_name(lookup=lookup)
    return UNSUPPORTED_INDEX_TYPES.get(col_type)

# One join operation per RENDERED column of these types, against the list view
# LOOKUP threshold. Kept here beside UNSUPPORTED_INDEX_TYPES because it is a
# property of the TYPE, and read from analysis/joins.py, which both the
# validator and the generator import.
#
# A DBML `ref` costs one too and is deliberately NOT listed: a lookup's DBML
# type is `int`, so it is invisible to a type test, and joins.py collects refs
# separately. `Created` and `Modified` are `datetime` and cost nothing.
JOIN_BEARING_TYPES = frozenset({"person"})
