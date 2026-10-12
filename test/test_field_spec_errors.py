# test/test_field_spec_errors.py
"""The named refusals `build_schema_json` raises for a field spec it cannot emit."""

from dataclasses import replace
from pathlib import Path
from typing import override

import pytest
from _builders import ID_PK, TITLE, table
from _packs import blocks, entities, pack, write_mapping
from _paths import FIXTURES

from dbml_sharepoint.analysis.resolve import resolve
from dbml_sharepoint.analysis.typemap import map_column as real_map_column
from dbml_sharepoint.extension import BaseExtension
from dbml_sharepoint.generators import jsgen
from dbml_sharepoint.generators.jsgen import FieldSpecError, build_schema_json
from dbml_sharepoint.jsonvalue import JsonValue
from dbml_sharepoint.model.mapping_loader import load_mapping
from dbml_sharepoint.model.mapping_types import MappingBundle
from dbml_sharepoint.model.parser import Column, Schema, Table, parse_dbml

_GOOD_BODY: dict[str, JsonValue] = {
    "__metadata": {"type": "SP.FieldUrl"}, "Title": "X", "FieldTypeKind": 11,
}


class _Expansion(BaseExtension):
    def __init__(self, fields: list[dict[str, JsonValue]]) -> None:
        self.fields = fields

    @override
    def expand_column(
        self, table: Table, column: Column, bundle: MappingBundle,
    ) -> list[dict[str, JsonValue]] | None:
        return self.fields


def _cross_site(tmp_path: Path) -> tuple[Schema, MappingBundle]:
    return pack(
        tmp_path,
        dbml=blocks(
            table("Unit", ID_PK),
            table("Risk", ID_PK, TITLE, "Unit int [ref: > Unit.Id]"),
        ),
        mapping=blocks(entities("Unit", "Risk"), """
            cross_site_reference_columns:
              - { entity: Risk, column: Unit }
        """),
    )


@pytest.mark.parametrize(
    "spec",
    [
        {"body": _GOOD_BODY},
        {"title": 7, "body": _GOOD_BODY},
        {"title": "X"},
        {"title": "X", "body": ["not", "an", "object"]},
        {"title": "X", "body": {"Title": "X"}},
        {"title": "X", "body": {"FieldTypeKind": True}},
        {"title": "X", "body": {"FieldTypeKind": "11"}},
        {"title": "X", "body": {**_GOOD_BODY, "Formula": 3}},
    ],
)
def test_an_extension_field_the_generator_cannot_read_is_refused(
    tmp_path: Path, spec: dict[str, JsonValue],
) -> None:
    schema, bundle = _cross_site(tmp_path)
    with pytest.raises(FieldSpecError, match=r"Risk\.Unit: expand_column must return fields"):
        build_schema_json(
            schema, bundle, "default", extension=_Expansion([spec]),
            resolved=resolve(schema, bundle.mapping),
        )


def test_an_extension_field_with_a_text_formula_is_accepted(tmp_path: Path) -> None:
    schema, bundle = _cross_site(tmp_path)
    spec: dict[str, JsonValue] = {
        "title": "X", "body": {**_GOOD_BODY, "Formula": "=1"},
    }
    built = build_schema_json(
        schema, bundle, "default", extension=_Expansion([spec]),
        resolved=resolve(schema, bundle.mapping),
    )
    risk = next(item for item in built["lists"] if item["title"] == "APP_Risk")
    assert [f["title"] for f in risk["fields_phase1"] if f["title"] == "X"] == ["X"]


def test_a_field_with_no_field_type_kind_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    schema, bundle = pack(
        tmp_path, dbml=table("Risk", ID_PK, TITLE, "Detail nvarchar"), mapping=entities("Risk"),
    )

    def without_kind(column: Column, enum_names: set[str]) -> object:
        return replace(real_map_column(column, enum_names), field_type_kind=None)

    monkeypatch.setattr(jsgen, "map_column", without_kind)
    with pytest.raises(FieldSpecError, match="has no FieldTypeKind"):
        build_schema_json(schema, bundle, "default", resolved=resolve(schema, bundle.mapping))


def test_a_deferred_lookup_that_yields_no_field_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_mapping(tmp_path, entities("Node"), name="mapping.yaml")
    schema = parse_dbml(FIXTURES / "self-ref.dbml")
    bundle = load_mapping(tmp_path / "mapping.yaml")

    def none_for_lookups(*args: object, **kwargs: object) -> None:
        return None

    monkeypatch.setattr(jsgen, "_field_body", none_for_lookups)
    with pytest.raises(FieldSpecError, match="a deferred lookup produced no field"):
        build_schema_json(schema, bundle, "default", resolved=resolve(schema, bundle.mapping))
