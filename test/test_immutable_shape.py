"""The properties the deploy refuses to change, and the gate that keeps them honest."""

from dbml_sharepoint.analysis.immutable_shape import (
    IMMUTABLE_FIELD_PROPERTIES,
    IMMUTABLE_LIST_PROPERTIES,
    IMMUTABLE_LOOKUP_PROPERTIES,
)


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
