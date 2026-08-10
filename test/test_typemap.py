# test/test_typemap.py
from pathlib import Path

import pytest
from _findings import only
from _packs import pack

from dbml_sharepoint.analysis.findings import FindingCode
from dbml_sharepoint.analysis.typemap import (
    describe_unknown_type,
    element_type,
    is_multi_value,
    map_column,
    supports_unique,
    unsupported_index_reason,
)
from dbml_sharepoint.model.parser import Column, Reference

ENUM_NAMES = {"status", "topic"}


def test_int_pk_increment_returns_skip() -> None:
    col = Column(name="Id", type="int", is_pk=True, is_auto_increment=True)
    assert map_column(col, ENUM_NAMES).kind == "Skip"


def test_int_with_ref_is_lookup() -> None:
    col = Column(
        name="Project",
        type="int",
        ref=Reference("Project", "Id"),
        required=True,
        unique=True,
    )
    field = map_column(col, ENUM_NAMES)
    assert field.kind == "Lookup"
    assert field.target_list == "Project"
    assert field.unique is True


def test_int_plain_is_number() -> None:
    col = Column(name="Counter", type="int")
    assert map_column(col, ENUM_NAMES).kind == "Number"


def test_nvarchar_is_text() -> None:
    col = Column(name="Title", type="nvarchar", required=True)
    field = map_column(col, ENUM_NAMES)
    assert field.kind == "Text"
    assert field.required is True


def test_longtext_is_plain_multiline_note() -> None:
    field = map_column(Column(name="OpaqueValue", type="longtext"), ENUM_NAMES)

    assert field.kind == "Note"
    assert field.field_type_kind == 3
    assert field.rich_text is False
    assert field.number_of_lines == 6


def test_richtext_is_note() -> None:
    assert map_column(Column(name="Notes", type="richtext"), ENUM_NAMES).kind == "Note"


def test_hyperlink_uses_field_url_display_format() -> None:
    field = map_column(Column(name="Link", type="hyperlink"), ENUM_NAMES)

    assert field.kind == "URL"
    assert field.field_type_kind == 11
    assert field.display_format == 0


def test_enum_typed_column_is_choice() -> None:
    col = Column(
        name="Status", type="status", required=True, unique=True, default="Open",
    )
    field = map_column(col, ENUM_NAMES)
    assert field.kind == "Choice"
    assert field.choices_enum == "status"
    assert field.unique is True


def test_unknown_type_raises() -> None:
    with pytest.raises(ValueError):
        map_column(Column(name="Bad", type="not_a_real_type"), ENUM_NAMES)


def test_legacy_choice_raises() -> None:
    with pytest.raises(ValueError, match="legacy 'choice' type"):
        map_column(Column(name="Status", type="choice"), ENUM_NAMES)


def test_calculated_text_maps_to_calculated() -> None:
    field = map_column(Column(name="RiskBand", type="calculated_text"), ENUM_NAMES)
    assert field.kind == "Calculated"
    assert field.field_type_kind == 17
    assert field.output_type == 2  # SP.FieldType Text
    assert field.required is False


def test_calculated_number_maps_to_calculated() -> None:
    field = map_column(Column(name="RiskScore", type="calculated_number"), ENUM_NAMES)
    assert field.kind == "Calculated"
    assert field.field_type_kind == 17
    assert field.output_type == 9  # SP.FieldType Number


def test_calculated_date_maps_to_calculated() -> None:
    field = map_column(Column(name="NextReviewDue", type="calculated_date"), ENUM_NAMES)
    assert field.kind == "Calculated"
    assert field.field_type_kind == 17
    assert field.output_type == 4  # SP.FieldType DateTime
    assert field.required is False


# --- multi-value enums ------------------------------------------------------

MULTI_ENUMS = {"audit_event", *ENUM_NAMES}


def test_an_enum_array_is_a_multichoice_field() -> None:
    """FieldType.MultiChoice is 15, and SharePoint's own read-back of a field
    created this way on 2026-08-10 reported TypeAsString="MultiChoice",
    FieldTypeKind=15 and Choices as Collection(Edm.String).

    The backing enum is the ELEMENT type: `Choices` is populated from the
    members of `audit_event`, not from an enum literally called
    `audit_event[]`, which is not a thing any schema declares.
    """
    field = map_column(Column(name="Events", type="audit_event[]"), MULTI_ENUMS)

    assert field.kind == "MultiChoice"
    assert field.field_type_kind == 15
    assert field.choices_enum == "audit_event"


def test_a_multi_value_column_keeps_its_required_flag() -> None:
    """`[not null]` composes normally on an array declaration -- pydbml parses
    it -- and Required is an ordinary field property SharePoint honours on a
    MultiChoice. Nothing about arity changes it."""
    field = map_column(
        Column(name="Events", type="audit_event[]", required=True), MULTI_ENUMS,
    )
    assert field.required is True


def test_a_misspelled_enum_array_is_still_refused_by_name() -> None:
    """THE argument for `enum_name[]` as the authored syntax: it was ALREADY a
    named build error that names the enum it is closest to, so adopting it
    widens an existing refusal instead of opening a new parse surface.

    That property is only worth anything if it survives the widening. A
    naming convention was rejected on the standing rule that a typo must
    never silently do nothing, and this is the assertion that keeps
    `audit_evnet[]` loud.
    """
    with pytest.raises(ValueError) as raised:
        map_column(Column(name="Events", type="audit_evnet[]"), MULTI_ENUMS)

    assert "unknown type 'audit_evnet[]'" in str(raised.value)
    assert "audit_event" in str(raised.value)


def test_an_array_of_something_that_is_not_an_enum_is_refused() -> None:
    """`person[]` and a multi-value lookup are a SEPARATE issue with a
    separate cost profile: both stay join-bearing, and whether one costs a
    single join or one per selected value is unmeasured. The arity predicate
    is deliberately type-agnostic, so this is the refusal that stops it
    letting them through the back door."""
    with pytest.raises(ValueError, match="unknown type 'person\\[\\]'"):
        map_column(Column(name="Owners", type="person[]"), MULTI_ENUMS)


def test_unique_on_a_multi_value_column_is_refused() -> None:
    """`[unique]` composes on an array declaration, so an author can write it.
    SharePoint cannot honour it: Microsoft lists "Choice (multi-valued)" as a
    type that cannot enforce unique values, and a POST setting
    EnforceUniqueValues on one returned HTTP 500 on 2026-08-10.

    The complaint has to be about uniqueness, not about the type being
    unknown -- which is what it said before the type was recognised.
    """
    with pytest.raises(ValueError) as raised:
        map_column(
            Column(name="Events", type="audit_event[]", unique=True), MULTI_ENUMS,
        )

    assert "[unique] is not supported" in str(raised.value)


def test_a_default_on_a_multi_value_column_is_refused() -> None:
    """DBML carries ONE scalar default and the write shape is a collection --
    `{"__metadata": {"type": "Collection(Edm.String)"}, "results": [...]}`,
    measured on 2026-08-10. There is no honest coercion between the two.

    Refused rather than dropped, because dropping it is the silent kind of
    wrong: the build goes green, the deploy verifies clean, and the column an
    author declared a default for simply does not have one.
    """
    with pytest.raises(ValueError) as raised:
        map_column(
            Column(name="Events", type="audit_event[]", default="View"), MULTI_ENUMS,
        )

    assert "default" in str(raised.value)
    assert "Events" in str(raised.value)


# --- unknown-type diagnosis -------------------------------------------------


def test_a_near_miss_scalar_is_suggested() -> None:
    """`persson` for `person` is a typo, and the supported set is a closed
    frozenset sitting next to the check -- suggesting from it is arithmetic
    over data we already hold, not a claim about SharePoint."""
    assert "person" in describe_unknown_type("persson", enums=())


def test_sql_vocabulary_gets_the_supported_set() -> None:
    """`decimal` is not a typo, it is somebody bringing SQL vocabulary to a
    DBML file. There is no near miss to offer, so the answer is the list --
    which is what teaches them `number`."""
    described = describe_unknown_type("decimal", enums=())
    assert "number" in described
    assert "nvarchar" in described


def test_a_misspelled_enum_is_suggested_from_the_schema() -> None:
    """The candidates must include the enums the file itself declares.

    A suggestion source of KNOWN_SCALARS alone cannot answer the commonest
    version of this mistake: the user wrote the name of their own enum
    slightly wrong.
    """
    described = describe_unknown_type("task_stat", enums=("task_status", "priority"))
    assert "task_status" in described


def test_the_diagnosis_never_mentions_the_source_tree() -> None:
    """The reader is a SharePoint admin editing a .dbml file.

    typemap's message used to end "Add it to typemap.py or declare it as an
    enum" -- half of which is an instruction to edit this repository.
    """
    described = describe_unknown_type("decimal", enums=())
    assert "typemap.py" not in described


def test_both_unknown_type_sites_say_the_same_thing(tmp_path: Path) -> None:
    """`build` reports this as a Finding and `report` reaches the raising
    site in typemap, because `report` does not validate. The same schema
    diagnosed two different ways is how a user comes to believe the two
    commands disagree about their file."""
    from dbml_sharepoint.analysis.validator import validate_all
    from dbml_sharepoint.extension import BaseExtension

    schema, bundle = pack(
        tmp_path,
        dbml="""
            Table Risk {
              Id int [pk, increment]
              Title nvarchar [not null]
              Cost decimal
            }
        """,
        mapping="""
            entities:
              Risk: { kind: List, base_template: 100, site_role: default }
        """,
    )
    findings = validate_all(schema, bundle, BaseExtension())
    message = only(findings, FindingCode.UNKNOWN_COLUMN_TYPE).message

    with pytest.raises(ValueError) as raised:
        map_column(
            next(c for c in schema.tables[0].columns if c.name == "Cost"), set(),
        )

    shared = describe_unknown_type("decimal", enums=())
    assert shared in message
    assert shared in str(raised.value)


# --- column arity -----------------------------------------------------------


def test_the_dbml_array_suffix_is_what_makes_a_type_multi_value() -> None:
    """One predicate, because arity is a property of the DECLARATION.

    `audit_event[]` is what pydbml hands over for `Events audit_event[]` --
    a literal type string, not a flag on the column -- so every check that
    wants to know "is this many-valued?" has exactly this question to ask.
    """
    assert is_multi_value("audit_event[]") is True
    assert is_multi_value("audit_event") is False
    assert is_multi_value("nvarchar") is False


def test_element_type_is_the_declaration_without_its_suffix() -> None:
    """What a member of the collection is, which is what has to be looked up
    in the schema's enums. A scalar is its own element type, so callers do
    not have to branch on arity before asking."""
    assert element_type("audit_event[]") == "audit_event"
    assert element_type("audit_event") == "audit_event"


def test_a_multi_value_column_can_never_be_indexed() -> None:
    """THE reason the arity predicate exists rather than a string entry.

    `UNSUPPORTED_INDEX_TYPES` is keyed by DBML type NAME, and `audit_event[]`
    is not a key in it -- nor is any other enum's array form, since the key
    would have to be minted per enum per schema. A membership test therefore
    looks like it covers the new type and silently does not.

    Documented refused by Microsoft ("Choice (multi-valued)" is listed as an
    unsupported index column type) and measured on 2026-08-10: a POST setting
    `Indexed: true` on a MultiChoice field was REFUSED -- "This column type is
    not supported for indexing." -- and read back `Indexed=false`. The control
    on the same run set `Indexed: true` on a single-value Choice in the same
    list and it stuck, so the refusal is the field's and not the probe's.
    """
    assert unsupported_index_reason("audit_event[]") == "Choice (multi-valued)"


def test_arity_beats_the_ref_shortcut_when_deciding_uniqueness() -> None:
    """`supports_unique` answered True for a multi-value column carrying a
    `ref`, because `col.ref is not None` short-circuits before anything looks
    at the type at all.

    Microsoft lists "Choice (multi-valued)", "Lookup (multi-valued)" and
    "Person (multi-valued)" as column types that cannot enforce unique
    values, and a probe on 2026-08-10 measured the Choice case: a POST
    setting EnforceUniqueValues on a MultiChoice field came back HTTP 500,
    "This column type is not supported for indexing".

    The scalar arm of this function gets the right answer for `audit_event[]`
    today only because that string is not a member of a frozenset of scalar
    names -- correct by accident, which is the state the arity predicate
    exists to end. The ref arm does not even get that.
    """
    multi_ref = Column(
        name="Owners", type="person[]", ref=Reference("Team", "Id"), unique=True,
    )
    assert supports_unique(multi_ref, ENUM_NAMES) is False


def test_the_index_denylist_still_answers_for_the_scalar_types() -> None:
    """The accessor replaces a dict membership test at three call sites, so
    it has to keep giving them the same human name for the same types -- and
    keep saying nothing about the types SharePoint can index."""
    assert unsupported_index_reason("longtext") == "Multiple lines of text (Note)"
    assert unsupported_index_reason("richtext") == "Multiple lines of text (Note)"
    assert unsupported_index_reason("hyperlink") == "Hyperlink"
    assert unsupported_index_reason("nvarchar") is None
    assert unsupported_index_reason("audit_event") is None
