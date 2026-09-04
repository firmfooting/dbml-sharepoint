# test/test_multilookup.py
"""A multi-value lookup, from one real build of `multilookup.dbml`.

Every assertion here reads an artifact the ordinary build path produced, not
a hand-assembled plan, because the failure this file guards against is a
layer that quietly drops the column: a `$select` that omits it, a Power Query
step that types a list as text, a create call that spells the arity in a way
SharePoint takes and ignores. A unit assertion over a plan cannot see any of
those, and the emitted script is where they show.

The tenant facts pinned here were measured on 2026-09-02
(`test/manual/multilookup-probe.js`) and are recorded in `analysis/typemap.py`.
"""

import json
from typing import Any

import pytest
from _paths import FIXTURES

from dbml_sharepoint.analysis.validator import validate_against_mapping
from dbml_sharepoint.generators.demogen import generate_demo_js
from dbml_sharepoint.generators.jsgen import build_schema_json, generate_deploy_js
from dbml_sharepoint.generators.reportgen import (
    generate_data_dictionary,
    generate_powerquery,
    generate_sql_views,
)
from dbml_sharepoint.model.mapping_loader import load_mapping
from dbml_sharepoint.model.mapping_types import MappingBundle
from dbml_sharepoint.model.parser import Schema, parse_dbml
from dbml_sharepoint.model.release import load_release

_SITE = "https://example.sharepoint.com/sites/t"


@pytest.fixture(scope="module")
def inputs() -> tuple[Schema, MappingBundle]:
    return (
        parse_dbml(FIXTURES / "multilookup.dbml"),
        load_mapping(FIXTURES / "multilookup-mapping.yaml"),
    )


def _matter_field(schema: Schema, bundle: MappingBundle, title: str) -> dict[str, Any]:
    schema_json = build_schema_json(schema, bundle, "default")
    matter = next(
        item for item in schema_json["lists"] if item["title"] == "APP_Matter"
    )
    return next(
        field for field in matter["fields_phase1"] if field["title"] == title
    )


def test_the_fixture_builds_clean(inputs: tuple[Schema, MappingBundle]) -> None:
    """The whole point of the fixture: `int[] [ref: > Party.Id]` is a shape
    the validator accepts, so every layer below is reached by a real build."""
    schema, bundle = inputs

    assert validate_against_mapping(schema, bundle) == []


def test_the_multi_value_lookup_is_created_as_xml(
    inputs: tuple[Schema, MappingBundle],
) -> None:
    """`AddField` + `AllowMultipleValues` is refused HTTP 400: the property
    does not exist on SP.FieldCreationInformation. createfieldasxml is the
    only route, so the emitted field carries an XML spec and no AddField
    parameters at all."""
    schema, bundle = inputs
    parties = _matter_field(schema, bundle, "Parties")

    assert parties["lookup_creation_xml"] == {
        "type": "LookupMulti",
        "name": "Parties",
        "show_field": "Title",
    }
    assert "lookup_creation_parameters" not in parties
    # FieldTypeKind 7 is SHARED with the single-value lookup; the arity is
    # AllowMultipleValues, and the entity type stays SP.FieldLookup.
    assert parties["body"]["FieldTypeKind"] == 7
    assert parties["body"]["AllowMultipleValues"] is True
    assert parties["body"]["__metadata"] == {"type": "SP.FieldLookup"}


def test_the_single_value_control_still_uses_addfield(
    inputs: tuple[Schema, MappingBundle],
) -> None:
    """The control. Only the multi arity diverges, and it diverges in one
    place: a single-value lookup keeps the AddField route it was measured on,
    and declares its arity false rather than omitting it."""
    schema, bundle = inputs
    owner = _matter_field(schema, bundle, "Owner")

    assert "lookup_creation_xml" not in owner
    assert owner["lookup_creation_parameters"]["FieldTypeKind"] == 7
    assert owner["body"]["AllowMultipleValues"] is False


def test_the_emitted_schema_xml_carries_mult_true(
    inputs: tuple[Schema, MappingBundle],
) -> None:
    """The XML attribute is `Mult`, not `AllowMultipleValues`.

    `AllowMultipleValues` is the REST property the field reads BACK as, and
    the two spellings are not interchangeable: SharePoint takes a <Field>
    element carrying an unknown attribute without complaint, so a wrong
    spelling here creates a single-value lookup, reads back byte-identical
    to what was asked for on every property the deploy checks, and is
    discovered by whoever tries to pick a second value on the form.
    """
    schema, bundle = inputs
    js = generate_deploy_js(
        schema=schema,
        bundle=bundle,
        release=load_release(FIXTURES / "release.yaml"),
        site_url=_SITE,
        site_role="default",
        source_dbml="multilookup.dbml",
        source_mtime="2026-09-02T00:00:00Z",
        generated_at="2026-09-02T00:00:00Z",
    )
    helper = js.split("async function createDeclaredLookupField", 1)[1]
    helper = helper.split("\n  }", 1)[0]

    assert '<Field Type="${spec.type}" Mult="TRUE"' in helper
    # Options 8 is AddFieldInternalNameHint, which is what keeps the internal
    # name equal to the declared one rather than to the display title.
    assert "Options: 8" in helper
    assert "/fields/createfieldasxml`" in helper


def test_the_demo_row_writes_a_results_object(
    inputs: tuple[Schema, MappingBundle],
) -> None:
    """A bare array is refused HTTP 400. The accepted shape writes through
    the same `<Name>Id` alias a single-value lookup uses, but the value is a
    `{ results: [...] }` object."""
    schema, bundle = inputs
    js = generate_demo_js(
        schema=schema,
        bundle=bundle,
        release=load_release(FIXTURES / "release.yaml"),
        site_url=_SITE,
        site_role="default",
        source_dbml="multilookup.dbml",
        generated_at="2026-09-02T00:00:00Z",
    )
    plan = json.loads(js.split("const DEMO_PLAN = ", 1)[1].split(";\n", 1)[0])
    matter = next(row for row in plan if row["key"] == "m1")
    parties = next(f for f in matter["fields"] if f["name"] == "Parties")

    assert parties["kind"] == "multi_ref"
    assert parties["value"] == ["acme", "globex"]
    assert parties["metadata_type"] == "Collection(Edm.Int32)"
    assert "body[`${f.name}Id`] = { results: refIds };" in js
    # And never the bare array, which is the shape the tenant refused.
    assert "body[`${f.name}Id`] = refIds;" not in js


def test_the_report_joins_the_ids_into_one_text_cell(
    inputs: tuple[Schema, MappingBundle],
) -> None:
    """The cell holds a LIST, so it is joined before anything types anything.

    The members are ids rather than strings, which is why the join converts
    them first: `Text.Combine` over a list of numbers raises, and a raising
    step fails the whole refresh rather than one column.
    """
    schema, bundle = inputs
    matter = generate_powerquery(schema, bundle, "default", site_url=_SITE)[
        "APP_Matter.pq"
    ]

    feed = matter.split("getbytitle('APP_Matter')/items\"", 1)[1]
    select = feed.split("?$select=", 1)[1].split("\"", 1)[0]
    assert "PartiesId" in select
    assert 'Text.Combine(List.Transform(_, Text.From), "; ")' in matter
    # No $expand: expanding a collection yields a nested table per row, and
    # nothing in this generator flattens one. The single-value control does
    # expand, so the absence is about arity and not about lookups.
    expand = feed.split("&$expand=", 1)[1].split("\"", 1)[0]
    assert "Owner" in expand
    assert "Parties" not in expand
    # A joined set has no bound worth guessing, and a CAST that overflows
    # truncates in silence.
    assert (
        "CAST(t.[PartiesId] AS NVARCHAR(MAX)) AS [PartiesId]"
        in generate_sql_views(schema, bundle, "default")
    )


def test_the_data_dictionary_says_the_cell_holds_ids(
    inputs: tuple[Schema, MappingBundle],
) -> None:
    """The dictionary is where a report author finds out what a column IS,
    and this one holds ids rather than titles, because the arm takes no
    $expand and so no title comes back with it."""
    schema, bundle = inputs
    row = next(
        line
        for line in generate_data_dictionary(
            schema, bundle, "default",
        ).splitlines()
        if line.startswith("| Parties |")
    )

    assert "Lookup (multiple) -> APP_Party" in row
    assert "a set of item ids" in row
    assert '"; "' in row
