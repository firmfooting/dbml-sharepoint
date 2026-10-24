"""A multi-person column (`person[]`), from one real build of `personmulti.dbml`.

Create route: Learn's Field element page lists the schema type `UserMulti`
("A User field that can contain more than one value")
https://learn.microsoft.com/en-us/sharepoint/dev/schema/field-element-list
and the deploy's `createfieldasxml` shape was accepted and read back as
TypeAsString UserMulti, AllowMultipleValues true (`field.version.fixture-payload-people-column`).
"""

import json

import pytest
from _findings import none_of, only
from _model import bundle as make_bundle
from _model import column as make_column
from _model import schema as make_schema
from _model import table as make_table
from _paths import FIXTURES

from dbml_sharepoint.analysis.findings import FindingCode
from dbml_sharepoint.analysis.reporting.plan import build_plans
from dbml_sharepoint.analysis.resolve import resolve
from dbml_sharepoint.analysis.typemap import (
    BASE_TYPE_AS_STRING_PAIRS,
    FIELD_TYPE_KIND_BY_KIND,
    MULTI_TYPE_AS_STRING_PAIRS,
    map_column,
)
from dbml_sharepoint.analysis.validator import validate, validate_against_mapping
from dbml_sharepoint.generators.jsgen import build_schema_json, generate_deploy_js
from dbml_sharepoint.generators.schema_types import FieldSpec
from dbml_sharepoint.model.mapping_loader import load_mapping
from dbml_sharepoint.model.mapping_types import DemoItem, MappingBundle
from dbml_sharepoint.model.parser import Schema, parse_dbml
from dbml_sharepoint.model.release import load_release
from dbml_sharepoint.testing.node import NODE, run_node


@pytest.fixture(scope="module")
def inputs() -> tuple[Schema, MappingBundle]:
    return (
        parse_dbml(FIXTURES / "personmulti.dbml"),
        load_mapping(FIXTURES / "personmulti-mapping.yaml"),
    )


def _field(schema: Schema, bundle: MappingBundle, title: str) -> FieldSpec:
    schema_json = build_schema_json(
        schema, bundle, "default", resolved=resolve(schema, bundle.mapping),
    )
    duty = next(item for item in schema_json["lists"] if item["title"] == "APP_Duty")
    return next(f for f in duty["fields_phase1"] if f["title"] == title)


def _codes(schema: Schema, bundle: MappingBundle) -> set[FindingCode]:
    return {f.code for f in validate_against_mapping(schema, bundle)}


def test_the_fixture_builds_clean(inputs: tuple[Schema, MappingBundle]) -> None:
    schema, bundle = inputs
    assert validate_against_mapping(schema, bundle) == []


def test_a_multi_person_column_is_a_user_field_allowing_several_values(
    inputs: tuple[Schema, MappingBundle],
) -> None:
    schema, bundle = inputs
    owners = _field(schema, bundle, "Owners")

    assert owners["user_creation_xml"] == {"type": "UserMulti", "name": "Owners"}
    assert owners["body"]["FieldTypeKind"] == FIELD_TYPE_KIND_BY_KIND["User"] == 20
    assert owners["body"]["AllowMultipleValues"] is True
    assert owners["body"]["__metadata"] == {"type": "SP.FieldUser"}


def test_the_single_person_control_is_unchanged(
    inputs: tuple[Schema, MappingBundle],
) -> None:
    schema, bundle = inputs
    owner = _field(schema, bundle, "Owner")

    assert "user_creation_xml" not in owner
    assert "AllowMultipleValues" not in owner["body"]


def test_the_deploy_creates_it_from_schema_xml_with_mult_true(
    inputs: tuple[Schema, MappingBundle],
) -> None:
    schema, bundle = inputs
    js = generate_deploy_js(
        schema=schema, bundle=bundle,
        release=load_release(FIXTURES / "release.yaml"),
        site_url="https://example.sharepoint.com/sites/t", site_role="default",
        source_dbml="personmulti.dbml", source_mtime="2026-10-13T00:00:00Z",
        generated_at="2026-10-13T00:00:00Z", resolved=resolve(schema, bundle.mapping),
    )
    helper = js.split("function declaredFieldCreateOp", 1)[1].split("\n  }", 1)[0]

    assert '<Field Type="${spec.type}" Mult="TRUE" UserSelectionMode="PeopleOnly"' in helper
    assert "Options: 8" in helper
    assert [20, "UserMulti"] in [list(p) for p in MULTI_TYPE_AS_STRING_PAIRS]


def test_arity_is_not_reconcilable_on_an_existing_person_column() -> None:
    """Nothing measured User's AllowMultipleValues flipping on a live column, so
    UserMulti is not collapsed onto User: a single/multi change aborts as an
    immutable TypeAsString mismatch. A lookup's arity is measured mutable."""
    collapsed = dict(BASE_TYPE_AS_STRING_PAIRS)
    assert "UserMulti" not in collapsed
    assert collapsed == {"LookupMulti": "Lookup"}


def test_the_report_selects_the_ids(inputs: tuple[Schema, MappingBundle]) -> None:
    schema, bundle = inputs
    plan = next(p for p in build_plans(schema, bundle, "default") if p.entity == "Duty")
    assert "OwnersId" in plan.selects
    assert ("OwnersId", False) in plan.multi_value_joins


def _duty_schema(*, unique: bool = False) -> Schema:
    return make_schema(make_table(
        "Duty", make_column("Title"), make_column("Owners", "person[]", unique=unique),
        note="Duty fixture.",
    ))


def test_a_multi_person_column_is_a_known_type() -> None:
    findings = validate(_duty_schema())
    none_of(findings, FindingCode.UNKNOWN_COLUMN_TYPE)


def test_an_unknown_array_type_is_still_unknown() -> None:
    schema = make_schema(make_table(
        "Duty", make_column("Title"), make_column("Owners", "blob[]"), note="Duty fixture.",
    ))
    only(
        validate(schema),
        FindingCode.UNKNOWN_COLUMN_TYPE,
    )


def test_unique_on_a_multi_person_column_names_the_person_type() -> None:
    findings = validate(_duty_schema(unique=True))
    finding = only(findings, FindingCode.MULTI_VALUE_UNIQUE_UNSUPPORTED)
    assert "Person (multi-valued)" in finding.message


def test_a_default_on_a_multi_person_column_is_refused() -> None:
    schema = make_schema(make_table(
        "Duty", make_column("Title"), make_column("Owners", "person[]", default="x"),
        note="Duty fixture.",
    ))
    only(
        validate(schema),
        FindingCode.MULTI_VALUE_DEFAULT_UNSUPPORTED,
    )
    with pytest.raises(ValueError, match="multi-value"):
        map_column(next(c for c in schema.tables[0].columns if c.name == "Owners"), set())


def test_a_demo_row_cannot_seed_a_multi_person_column() -> None:
    bundle = make_bundle(
        entities=["Duty"],
        demo_items={"Duty": [DemoItem(key="d1", values={
            "Title": "[DEMO] Row", "Owners": ["@me"],
        })]},
    )
    only(
        validate_against_mapping(_duty_schema(), bundle),
        FindingCode.DEMO_PERSON_VALUE_UNSUPPORTED,
    )


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_the_emitted_create_op_runs_and_builds_the_xml_request(
    inputs: tuple[Schema, MappingBundle],
) -> None:
    """Executes the emitted function, not just its text."""
    schema, bundle = inputs
    js = generate_deploy_js(
        schema=schema, bundle=bundle,
        release=load_release(FIXTURES / "release.yaml"),
        site_url="https://example.sharepoint.com/sites/t", site_role="default",
        source_dbml="personmulti.dbml", source_mtime="2026-10-13T00:00:00Z",
        generated_at="2026-10-13T00:00:00Z", resolved=resolve(schema, bundle.mapping),
    )
    fn = "function declaredFieldCreateOp" + js.split("function declaredFieldCreateOp", 1)[1].split(
        "\n  }\n", 1,
    )[0] + "\n  }\n"
    owners = json.dumps(_field(schema, bundle, "Owners"))
    owner = json.dumps(_field(schema, bundle, "Owner"))
    script = (
        "const odataName = (n) => encodeURIComponent(String(n).replace(/'/g, \"''\"));\n"
        + fn
        + f"console.log(JSON.stringify([declaredFieldCreateOp('L', {owners}, null),"
        f" declaredFieldCreateOp('L', {owner}, null)]));"
    )
    multi, single = json.loads(run_node(script).strip().splitlines()[-1])

    assert multi["path"].endswith("/fields/createfieldasxml")
    assert multi["body"] == {"parameters": {
        "SchemaXml": '<Field Type="UserMulti" Mult="TRUE" UserSelectionMode="PeopleOnly" '
                     'DisplayName="Owners" Name="Owners"/>',
        "Options": 8,
    }}
    assert single["path"].endswith("/fields")
    assert single["body"]["FieldTypeKind"] == 20
