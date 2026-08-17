# test/test_provenance_marker.py
"""The two properties the adoption gate rests on.

The gate is a substring search, so it is only sound while no marker can sit
inside another, and while a marker copied to a different object stops
matching. Both were false before #240 and #241.
"""

import itertools

import pytest
from _findings import none_of, only
from _model import bundle as make_bundle
from _model import schema as make_schema
from _model import table as make_table

from dbml_sharepoint.analysis import provenance
from dbml_sharepoint.analysis.findings import Finding, FindingCode
from dbml_sharepoint.analysis.group_description import marker_for_group
from dbml_sharepoint.analysis.list_description import marker_for
from dbml_sharepoint.analysis.role_definition_description import marker_for_level
from dbml_sharepoint.analysis.validator import validate_against_mapping
from dbml_sharepoint.model.mapping_types import (
    CustomPermissionLevel,
    PermissionsConfig,
)

# Adversarial on purpose: names that differ only by a suffix, by a separator,
# or by the characters the old fold collapsed.
FAMILIES = ["risk", "risk2", "risk-v2", "risk_v2", "a", "ab", "routine_checks"]
NAMES = ["Owners", "Owners2", "Owners Extra", "O", "Risk", "Risk Owners"]
KINDS = [provenance.LIST_KIND, provenance.GROUP_KIND, provenance.LEVEL_KIND]


def _every_marker() -> list[str]:
    markers = [
        provenance.marker_for_object(kind=k, name=n, family=f)
        for f in FAMILIES for k in KINDS for n in NAMES
    ]
    # The tool-owned form carries no family and must stay distinguishable.
    markers += [
        provenance.marker_for_object(kind=provenance.GROUP_KIND, name=n, family=None)
        for n in NAMES
    ]
    return markers


def test_no_marker_is_a_substring_of_another() -> None:
    """`from risk.` used to match inside `from risk.v2.`, so family `risk`
    adopted a populated group belonging to family `risk.v2`."""
    markers = _every_marker()
    assert len(markers) == len(set(markers)), "markers are not distinct"

    violations = [
        (a, b) for a, b in itertools.permutations(set(markers), 2) if a in b
    ]
    assert not violations, (
        f"{len(violations)} marker(s) sit inside another; first: {violations[0]}"
    )


def test_the_terminator_appears_exactly_once() -> None:
    """Prefix-freeness rests on it, so it is pinned rather than assumed."""
    for m in _every_marker():
        assert m.count(provenance.MARKER_TERMINATOR) == 1, m
        assert m.endswith(provenance.MARKER_TERMINATOR), m


@pytest.mark.parametrize(
    ("kind", "one", "other"),
    [
        (provenance.LIST_KIND, "Risk", "Issue"),
        (provenance.GROUP_KIND, "Risk Owners", "Risk Readers"),
        (provenance.LEVEL_KIND, "Risk Contributor", "Risk Reader"),
    ],
)
def test_a_marker_copied_to_another_object_stops_matching(
    kind: str, one: str, other: str,
) -> None:
    """Descriptions are operator-editable and get copied between objects.

    Argo CD adopted resources it did not own because charts copied its
    tracking label; the fix was to name the object inside the marker.
    """
    copied = provenance.marker_for_object(kind=kind, name=one, family="risk")
    expected = provenance.marker_for_object(kind=kind, name=other, family="risk")
    description = f"Some declared text. {copied}"

    # The control: the object it was copied FROM still matches, so the test
    # is not passing because the marker is absent.
    assert copied in description
    assert expected not in description, (
        f"a description copied from {one!r} still satisfies {other!r}'s gate"
    )


def test_each_surface_builds_from_the_one_authority() -> None:
    """Three surfaces, one grammar, so a change cannot reach two of them."""
    assert marker_for("risk", "Risk") == provenance.marker_for_object(
        kind=provenance.LIST_KIND, name="Risk", family="risk",
    )
    assert marker_for_group("Risk Owners", "risk") == provenance.marker_for_object(
        kind=provenance.GROUP_KIND, name="Risk Owners", family="risk",
    )
    assert marker_for_level("risk", "Risk Contributor") == provenance.marker_for_object(
        kind=provenance.LEVEL_KIND, name="Risk Contributor", family="risk",
    )


def test_a_tool_owned_group_marker_carries_no_family_but_names_itself() -> None:
    """Any family may adopt these, so they carry no family. They still name
    the group, or a description copied between two of them would adopt."""
    reader = marker_for_group("dbml Enterprise Readers", "risk")
    admin = marker_for_group("dbml List Administrators", "other-family")
    assert "from risk" not in reader
    assert reader != admin
    assert admin not in reader and reader not in admin


# --- the rules that keep the grammar prefix-free -------------------------


def _marker_findings(
    project_name: str, *, level_name: str = "XX Level",
) -> list[Finding]:
    """Validate a one-entity mapping whose family comes from `project_name`."""
    return validate_against_mapping(
        make_schema(make_table("Risk"), project_name=project_name),
        make_bundle(
            entities=["Risk"],
            permissions=PermissionsConfig(
                levels=[CustomPermissionLevel(
                    name=level_name, description="test",
                    base_permissions=["ViewListItems"],
                )],
                groups=[], default_policy=None, overrides={},
            ),
        ),
    )


def _marker_codes(findings: list[Finding]) -> set[FindingCode]:
    """Only the marker codes, so an unrelated fixture finding cannot mask
    which of these rules fired."""
    return {f.code for f in findings if f.code.value.startswith("marker_")}


def test_a_project_name_holding_the_terminator_is_refused() -> None:
    """`from risk.` sat inside `from risk.v2.`, so family `risk` adopted a
    populated group belonging to family `risk.v2`."""
    only(_marker_findings("risk.v2"), FindingCode.MARKER_FIELD_HAS_RESERVED_TEXT)


def test_a_level_name_holding_the_terminator_is_refused() -> None:
    """The object name is interpolated too, so it can split a marker the
    same way the family name can."""
    only(
        _marker_findings("risk_register", level_name="XX.Level"),
        FindingCode.MARKER_FIELD_HAS_RESERVED_TEXT,
    )


def test_a_schema_with_no_project_name_is_refused() -> None:
    """Nothing to attribute a provisioned object to, so rollback cannot tell
    its own lists from anyone else's."""
    only(_marker_findings(""), FindingCode.MARKER_FAMILY_MISSING)


def test_an_ordinary_project_name_fires_neither() -> None:
    """The complement, so the rules are not passing by refusing everything."""
    findings = _marker_findings("routine_checks")
    none_of(findings, FindingCode.MARKER_FIELD_HAS_RESERVED_TEXT)
    none_of(findings, FindingCode.MARKER_FAMILY_MISSING)


def test_a_name_embedding_the_marker_prefix_is_refused() -> None:
    """Refusing only the terminator was not enough.

    A family name holding the whole prefix produces a marker carrying
    another family's complete marker as a suffix, with no `.` anywhere, so
    that family's gate adopts the object.
    """
    only(
        _marker_findings("x Provisioned by dbml-sharepoint from risk"),
        FindingCode.MARKER_FIELD_HAS_RESERVED_TEXT,
    )


def test_a_marker_longer_than_its_field_is_refused() -> None:
    """The budget clamps to zero, so an empty description passed and
    generation emitted a marker SharePoint refuses part-way through.

    A family this long trips the list and the level ceiling at once, so the
    assertion is that every finding is this code rather than that there is
    exactly one.
    """
    marker_codes = _marker_codes(_marker_findings("f" * 480, level_name="Level"))
    assert marker_codes == {FindingCode.MARKER_LONGER_THAN_THE_FIELD}


def test_a_list_marker_longer_than_its_field_is_refused() -> None:
    """The same zero-clamp gap as the level case, found by looking for it
    rather than by being told: note_budget clamps too."""
    marker_codes = _marker_codes(_marker_findings("f" * 230))
    assert marker_codes == {FindingCode.MARKER_LONGER_THAN_THE_FIELD}
