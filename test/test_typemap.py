# test/test_typemap.py
from collections.abc import Callable
from pathlib import Path

import pytest
from _findings import only
from _packs import pack

from dbml_sharepoint.analysis.findings import FindingCode
from dbml_sharepoint.analysis.typemap import (
    describe_unknown_type,
    is_boolean,
    is_hyperlink,
    is_legacy_choice,
    is_person,
    map_column,
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


# --- The type-identity predicates and the single-authority pin ---------------


def test_the_predicates_answer_the_declared_type() -> None:
    assert is_boolean("boolean")
    assert not is_boolean("int")
    assert is_person("person")
    assert not is_person("nvarchar")
    assert is_hyperlink("hyperlink")
    assert not is_hyperlink("richtext")
    assert is_legacy_choice("choice")
    assert not is_legacy_choice("status")


@pytest.mark.parametrize(
    "predicate", [is_boolean, is_person, is_hyperlink, is_legacy_choice],
)
def test_an_undeclared_type_is_none_of_them(
    predicate: Callable[[str | None], bool],
) -> None:
    """`None` is what `types_by_col.get(name)` returns for a column the mapping
    names and the schema does not, and both demo readers hold exactly that.
    Answering True for an absent type would route an unknown column down a
    typed path."""
    assert not predicate(None)


@pytest.mark.parametrize(
    ("declared", "kind"),
    [("boolean", "Boolean"), ("person", "User"), ("hyperlink", "URL")],
)
def test_the_mapper_itself_goes_through_the_predicates(
    declared: str, kind: str,
) -> None:
    """A predicate `map_column` does not consult is a second opinion, free to
    drift from the mapping it claims to describe -- which is the bug #101 is
    about, relocated. These three cases were lifted out of `_scalar`'s match
    statement precisely so there is one answer, so they are pinned here."""
    assert map_column(Column(name="X", type=declared), ENUM_NAMES).kind == kind


def test_the_mapper_refuses_legacy_choice_through_the_predicate() -> None:
    with pytest.raises(ValueError, match="legacy 'choice' type"):
        map_column(Column(name="Status", type="choice"), ENUM_NAMES)

