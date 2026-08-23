"""The group Description composition, and the budget it leaves a human note."""

import pytest

from dbml_sharepoint.analysis.group_description import (
    FAMILY_MARKER_TEMPLATE,
    GROUP_MARKER_GROWTH_RESERVE,
    TOOL_OWNED_GROUP_NAMES,
    description_budget,
    group_description,
    marker_for_group,
    shared_marker_for,
)
from dbml_sharepoint.analysis.limits import MAX_GROUP_DESCRIPTION
from dbml_sharepoint.analysis.provenance import MARKER_PREFIX


def test_a_tool_owned_group_gets_a_family_less_marker_naming_itself() -> None:
    """The shared groups span families, so naming one family would be false.

    They still name the group, or a description copied between the two would
    satisfy the other's adoption gate.
    """
    reader = marker_for_group("dbml Enterprise Readers", "risk-register")
    admin = marker_for_group("dbml List Administrators", "incident-management")

    assert reader == shared_marker_for("dbml Enterprise Readers")
    assert admin == shared_marker_for("dbml List Administrators")
    assert "risk-register" not in reader
    assert "incident-management" not in admin
    assert reader != admin


def test_a_family_group_gets_the_family_marker() -> None:
    assert marker_for_group("RR Risk Managers", "risk-register") == (
        "Provisioned by dbml-sharepoint from risk-register for group RR Risk Managers."
    )


def test_both_shapes_start_with_the_detection_prefix() -> None:
    """The deploy tests one prefix; it never learns which shape to expect."""
    assert shared_marker_for("dbml Enterprise Readers").startswith(MARKER_PREFIX)
    assert FAMILY_MARKER_TEMPLATE.startswith(MARKER_PREFIX)
    assert marker_for_group("RR Risk Managers", "risk-register").startswith(MARKER_PREFIX)


def test_the_composed_description_is_note_then_marker() -> None:
    composed = group_description(
        "Staff who rate risks.", group_name="RR Risk Managers", family="risk-register",
    )
    assert composed == (
        "Staff who rate risks. "
            "Provisioned by dbml-sharepoint from risk-register for group RR Risk Managers."
    )


def test_an_empty_declaration_returns_the_marker_alone() -> None:
    """Not a leading space. ' Provisioned by...' is not what 'no note' looks like."""
    composed = group_description("", group_name="dbml Enterprise Readers", family="x")
    assert composed == shared_marker_for("dbml Enterprise Readers")


def test_the_note_is_clamped_before_the_marker_is_appended() -> None:
    """Appending first and clamping the result cuts the tail, and the tail is the marker."""
    budget = description_budget("RR Risk Managers", "risk-register")
    composed = group_description(
        "z" * (budget + 50), group_name="RR Risk Managers", family="risk-register",
    )
    assert composed.endswith(
        "Provisioned by dbml-sharepoint from risk-register for group RR Risk Managers."
    )
    assert len(composed) <= MAX_GROUP_DESCRIPTION - GROUP_MARKER_GROWTH_RESERVE


def test_the_budget_reserves_room_for_the_marker_to_grow() -> None:
    budget = description_budget("RR Risk Managers", "risk-register")
    marker = marker_for_group("RR Risk Managers", "risk-register")
    assert budget == MAX_GROUP_DESCRIPTION - len(marker) - 1 - GROUP_MARKER_GROWTH_RESERVE


#: The reserve, written out rather than imported. See the test below for why.
_PINNED_GROUP_RESERVE = 21


def test_a_description_the_budget_accepts_survives_the_marker_growing() -> None:
    """The reserve, asserted as the invariant it buys rather than as arithmetic.

    Every other test of this constant either asks `description_budget` what
    fits or computes its expectation from `GROUP_MARKER_GROWTH_RESERVE`, so
    both sides move together and the reserve can be set to zero with all of
    them green. Measured 2026-08-23 against 838c727: zeroing this constant and
    `LEVEL_MARKER_GROWTH_RESERVE` leaves the entire suite passing.

    So the number is written out here instead, and what is asserted is the
    property the constant exists for: a description this build accepts today
    still fits beside a marker 21 characters longer than the current one.

    Both marker shapes are covered. A tool-owned group's marker carries no
    family name, so it is the shorter of the two and buys the larger budget.
    """
    for group_name, family in (
        ("RR Risk Managers", "risk-register"),
        ("dbml Enterprise Readers", "risk-register"),
    ):
        marker = marker_for_group(group_name, family)
        accepted = "z" * description_budget(group_name, family)
        grown = marker + "v" * _PINNED_GROUP_RESERVE
        assert len(f"{accepted} {grown}") <= MAX_GROUP_DESCRIPTION, (
            f"{group_name}: a description of {len(accepted)} characters is "
            f"accepted today but would not fit beside a marker "
            f"{_PINNED_GROUP_RESERVE} characters longer, so the reserve no "
            f"longer holds back what it claims to."
        )


def test_an_absurd_family_name_yields_a_zero_budget_not_a_negative_one() -> None:
    """A negative budget makes note[:budget] keep everything but the last N chars."""
    assert description_budget("RR Risk Managers", "f" * MAX_GROUP_DESCRIPTION) == 0


def test_a_zero_budget_still_returns_the_marker_alone() -> None:
    composed = group_description(
        "a note", group_name="RR Risk Managers", family="f" * MAX_GROUP_DESCRIPTION,
    )
    assert composed == marker_for_group("RR Risk Managers", "f" * MAX_GROUP_DESCRIPTION)


@pytest.mark.parametrize("name", sorted(TOOL_OWNED_GROUP_NAMES))
def test_every_tool_owned_name_is_actually_shipped(name: str) -> None:
    """A typo here silently downgrades a shared group to the family marker."""
    from dbml_sharepoint.catalogue import SOLUTIONS_DIR

    mappings = (SOLUTIONS_DIR).rglob("20-configure/mapping.yaml")
    assert any(name in m.read_text(encoding="utf-8") for m in mappings)
