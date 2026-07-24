# test/test_typemap.py
import pytest

from dbml_sharepoint.analysis.typemap import map_column
from dbml_sharepoint.model.parser import Column, Reference

ENUM_NAMES = {"status", "topic"}


def test_int_pk_increment_returns_skip() -> None:
    col = Column(name="Id", type="int", is_pk=True, is_auto_increment=True)
    assert map_column(col, ENUM_NAMES).kind == "Skip"


def test_int_with_ref_is_lookup() -> None:
    col = Column(name="Project", type="int", ref=Reference("Project", "Id"), required=True)
    field = map_column(col, ENUM_NAMES)
    assert field.kind == "Lookup"
    assert field.target_list == "Project"


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
    col = Column(name="Status", type="status", required=True, default="Open")
    field = map_column(col, ENUM_NAMES)
    assert field.kind == "Choice"
    assert field.choices_enum == "status"


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
