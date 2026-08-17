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
    """A non-lookup field's shape carries neither, so folding them in would
    describe a shape that is never read."""
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
    assert end > 0, name
    return body[:end]


def _compared_properties(source: str, name: str) -> set[str]:
    return set(re.findall(r"actual\.([A-Za-z]+)", _function_body(source, name)))


def test_the_field_assertions_and_the_vocabulary_cover_the_same_properties() -> None:
    """Both directions: an unenforced record entry, and an unrecorded refusal."""
    compared = _compared_properties(_deploy_js(), "assertFieldImmutableShape")
    assert compared == set(IMMUTABLE_FIELD_PROPERTIES) | set(IMMUTABLE_LOOKUP_PROPERTIES)


def test_the_list_assertion_and_the_vocabulary_cover_the_same_properties() -> None:
    compared = _compared_properties(_deploy_js(), "assertListImmutableShape")
    assert compared == set(IMMUTABLE_LIST_PROPERTIES)


def test_every_field_property_is_in_the_select_it_is_read_with() -> None:
    """A property no probe selects would compare against undefined and pass."""
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
