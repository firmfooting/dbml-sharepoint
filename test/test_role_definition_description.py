"""The permission level Description composition, and the budget it leaves a human note."""

from dbml_sharepoint.analysis.limits import MAX_ROLE_DEFINITION_DESCRIPTION
from dbml_sharepoint.analysis.provenance import MARKER_PREFIX
from dbml_sharepoint.analysis.role_definition_description import (
    LEVEL_MARKER_GROWTH_RESERVE,
    level_description,
    level_description_budget,
    marker_for_level,
)


def test_the_marker_names_the_family_and_the_level() -> None:
    assert marker_for_level("risk-register", "Risk Contributor") == (
        "Provisioned by dbml-sharepoint from risk-register for level Risk Contributor."
    )


def test_the_marker_opens_with_the_shared_prefix() -> None:
    """The deploy tests one prefix; it never learns which surface it came from."""
    assert marker_for_level("risk-register", "Risk Contributor").startswith(MARKER_PREFIX)


def test_the_composed_description_is_note_then_marker() -> None:
    composed = level_description(
        "Rates risks on a shared list.",
        family="risk-register", level_name="Risk Contributor",
    )
    assert composed == (
        "Rates risks on a shared list. "
            "Provisioned by dbml-sharepoint from risk-register for level Risk Contributor."
    )


def test_an_empty_declaration_returns_the_marker_alone() -> None:
    """Not a leading space. ' Provisioned by...' is not what 'no note' looks like."""
    composed = level_description("", family="risk-register", level_name="Risk Contributor")
    assert composed == marker_for_level("risk-register", "Risk Contributor")


def test_the_note_is_clamped_before_the_marker_is_appended() -> None:
    """Appending first and clamping the result cuts the tail, and the tail is the marker."""
    budget = level_description_budget("risk-register", "Risk Contributor")
    composed = level_description(
        "z" * (budget + 50), family="risk-register", level_name="Risk Contributor",
    )
    assert composed.endswith(
        "Provisioned by dbml-sharepoint from risk-register for level Risk Contributor."
    )
    assert len(composed) <= MAX_ROLE_DEFINITION_DESCRIPTION - LEVEL_MARKER_GROWTH_RESERVE


def test_the_budget_reserves_room_for_the_marker_to_grow() -> None:
    budget = level_description_budget("risk-register", "Risk Contributor")
    marker = marker_for_level("risk-register", "Risk Contributor")
    assert budget == (
        MAX_ROLE_DEFINITION_DESCRIPTION - len(marker) - 1 - LEVEL_MARKER_GROWTH_RESERVE
    )


def test_an_absurd_family_name_yields_a_zero_budget_not_a_negative_one() -> None:
    """A negative budget makes note[:budget] keep everything but the last N chars."""
    absurd = "f" * MAX_ROLE_DEFINITION_DESCRIPTION
    assert level_description_budget(absurd, "Risk Contributor") == 0


def test_a_zero_budget_still_returns_the_marker_alone() -> None:
    family = "f" * MAX_ROLE_DEFINITION_DESCRIPTION
    composed = level_description(
        "a note", family=family, level_name="Risk Contributor",
    )
    assert composed == marker_for_level(family, "Risk Contributor")
