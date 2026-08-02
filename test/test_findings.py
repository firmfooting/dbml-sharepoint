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


def test_validator_still_exports_finding_and_severity() -> None:
    """`extension.py` documents `Finding` as the reporting type and
    `manifestgen` consumes it. Extension authors import it from `validator`.
    """
    from dbml_sharepoint.analysis import findings, validator

    assert validator.Finding is findings.Finding
    assert validator.Severity is findings.Severity


def test_severity_is_declared_exactly_once() -> None:
    """It was declared twice, in validator.py and forms.py, with identical
    bodies. Two spellings of one type is how they drift."""
    import ast

    from _paths import PACKAGE

    declared = []
    for path in PACKAGE.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.TypeAlias) and node.name.id == "Severity":
                declared.append(path.name)
    assert declared == ["findings.py"], declared
