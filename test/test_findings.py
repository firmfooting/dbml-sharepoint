"""The finding vocabulary.

A finding's identity is its code. The message is prose for a human and may be
reworded at any time; nothing may key off it. `Location` exists so the dotted
path in a message is derived from structured data rather than being the only
place that data exists.
"""

import pytest

from dbml_sharepoint.analysis.findings import (
    Finding,
    FindingCode,
    Location,
    Section,
)


def test_location_renders_the_dotted_path() -> None:
    loc = Location(Section.VIEWS, entity="Risk", view="Open")
    assert loc.path == "views[Risk].Open"


def test_location_renders_a_column_path() -> None:
    loc = Location(Section.COLUMN_FORMATTING, entity="Risk", column="Status")
    assert loc.path == "column_formatting[Risk].Status"


def test_location_renders_a_bare_section() -> None:
    assert Location(Section.ENTITIES, entity="Risk").path == "entities[Risk]"


def test_location_appends_a_sub_path() -> None:
    loc = Location(Section.FORM_VISIBILITY, entity="Risk", column="Status", sub="when")
    assert loc.path == "form_visibility[Risk].Status.when"


def test_finding_is_hashable_and_frozen() -> None:
    """Findings go into sets in tests, and nothing may mutate one after the
    check that produced it has returned."""
    f = Finding(
        code=FindingCode.UNKNOWN_ENTITY,
        severity="error",
        message="views[Risk]: unknown entity.",
        location=Location(Section.VIEWS, entity="Risk"),
    )
    assert {f, f} == {f}
    with pytest.raises(AttributeError):
        f.severity = "warning"  # type: ignore[misc]


def test_every_code_is_screaming_snake_case() -> None:
    """The code is an API. A typo in one is a silent no-match in a test."""
    for code in FindingCode:
        assert code.name == code.name.upper()
        assert code.value == code.name.lower()
