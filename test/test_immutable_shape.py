"""The properties the deploy refuses to change, and the gate that keeps them honest."""

import re

from _paths import FIXTURES, JINJA_TEMPLATES

from dbml_sharepoint.analysis.immutable_shape import (
    IMMUTABLE_FIELD_PROPERTIES,
    IMMUTABLE_LIST_PROPERTIES,
    IMMUTABLE_LOOKUP_PROPERTIES,
)
from dbml_sharepoint.generators.jsgen import generate_deploy_js
from dbml_sharepoint.model.mapping_loader import load_mapping
from dbml_sharepoint.model.parser import parse_dbml
from dbml_sharepoint.model.release import load_release

PROBES = JINJA_TEMPLATES / "deploy" / "_shape_probes.js.j2"


def test_the_immutable_field_properties_are_the_ones_read_for_every_field() -> None:
    assert IMMUTABLE_FIELD_PROPERTIES == (
        "InternalName",
        "TypeAsString",
        "ReadOnlyField",
        "Sealed",
    )


def test_the_immutable_lookup_properties_are_separate_because_the_probe_is() -> None:
    """Kept separate because only a lookup field's shape carries them.

    A non-lookup field's shape carries neither, so folding them into the field
    set would describe a shape that is never read.
    """
    assert IMMUTABLE_LOOKUP_PROPERTIES == ("LookupList", "LookupField")


def test_the_immutable_list_properties_are_the_ones_the_deploy_asserts() -> None:
    assert IMMUTABLE_LIST_PROPERTIES == ("BaseTemplate",)


def _deploy_js() -> str:
    return generate_deploy_js(
        schema=parse_dbml(FIXTURES / "simple.dbml"),
        bundle=load_mapping(FIXTURES / "sharepoint-mapping.yaml"),
        release=load_release(FIXTURES / "release.yaml"),
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default",
        source_dbml="simple.dbml",
        source_mtime="2026-05-04T00:00:00Z",
        generated_at="2026-05-04T00:00:00Z",
    )


def _function_body(source: str, name: str) -> str:
    """The body of a function declared at two-space indent.

    Both asserts sit at that indent inside the IIFE, so the first `\\n  }`
    after the declaration is the function's own closing brace.
    """
    start = source.index(f"function {name}")
    body = source[start:]
    end = body.index("\n  }")
    return body[:end]


def _compared_properties(source: str, name: str) -> set[str]:
    """The properties the named assertion reads in guard position.

    The lookbehind drops `${actual.X}` interpolations, so naming a property in an
    error message does not count as comparing it. This pins which properties are
    still compared, and nothing more: changing a `!==` to `===` leaves the
    property in guard position and this test green. The golden fixture and review
    cover whether a comparison is correct.
    """
    return set(re.findall(r"(?<!\$\{)actual\.([A-Za-z]+)", _function_body(source, name)))


def test_the_field_assertions_and_the_vocabulary_cover_the_same_properties() -> None:
    """The assertion and the vocabulary have to name the same properties.

    A name listed here that the assertion no longer guards means the deploy quietly
    stopped refusing it. A property the assertion guards that is missing from the
    vocabulary means this set no longer describes what the deploy does.
    """
    compared = _compared_properties(_deploy_js(), "assertFieldImmutableShape")
    assert compared == set(IMMUTABLE_FIELD_PROPERTIES) | set(IMMUTABLE_LOOKUP_PROPERTIES)


def test_the_list_assertion_and_the_vocabulary_cover_the_same_properties() -> None:
    compared = _compared_properties(_deploy_js(), "assertListImmutableShape")
    assert compared == set(IMMUTABLE_LIST_PROPERTIES)


def test_every_field_property_is_in_the_select_it_is_read_with() -> None:
    """A cheaper and earlier signal than the run-time abort that covers the same gap.

    `_shape_probes.js.j2` type-checks every one of these properties and throws
    'shape probe returned an invalid response', so dropping one from the select
    fails loudly on a live site rather than passing. This test says so at build
    time, and it still holds if those run-time validators are ever weakened.
    """
    probe = PROBES.read_text(encoding="utf-8")
    select = re.search(r"const _FIELD_SHAPE_SELECT = \[(.*?)\]", probe, re.DOTALL)
    assert select is not None
    for name in IMMUTABLE_FIELD_PROPERTIES:
        assert f"'{name}'" in select.group(1), name


def test_every_lookup_property_is_in_the_conditional_probe_select() -> None:
    """The one literal $select in the file is the lookup probe's."""
    probe = PROBES.read_text(encoding="utf-8")
    literal_selects = re.findall(r"\?\$select=([A-Za-z][A-Za-z,]*)`", probe)
    assert literal_selects == [",".join(IMMUTABLE_LOOKUP_PROPERTIES)]


def test_every_list_property_is_in_the_select_it_is_read_with() -> None:
    probe = PROBES.read_text(encoding="utf-8")
    select = re.search(
        r"const select = \[(.*?)\]", _function_body(probe, "readListShape"), re.DOTALL,
    )
    assert select is not None
    for name in IMMUTABLE_LIST_PROPERTIES:
        assert f"'{name}'" in select.group(1), name
