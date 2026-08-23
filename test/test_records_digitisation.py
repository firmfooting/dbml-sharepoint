"""Contracts specific to the records-digitisation solution family."""

from functools import cache

from _paths import SOLUTION_TEMPLATES

from dbml_sharepoint.model.conditions import Condition, Group, Leaf
from dbml_sharepoint.model.mapping_loader import load_mapping
from dbml_sharepoint.model.mapping_types import MappingBundle
from dbml_sharepoint.model.parser import Schema, parse_dbml

ROOT = SOLUTION_TEMPLATES / "records-digitisation"
MAPPING = ROOT / "20-configure" / "mapping.yaml"
SCHEMA = ROOT / "10-design" / "schema.dbml"
OBLIGATION_VERDICTS = {
    "Suitable with named configuration",
    "Interim only - export with metadata proven",
}
PERMISSION_SCOPE_SOURCE = (
    "https://learn.microsoft.com/en-us/sharepoint/understanding-permission-levels"
    "#overview-and-permissions-inheritance"
)


@cache
def _bundle() -> MappingBundle:
    return load_mapping(MAPPING)


@cache
def _schema() -> Schema:
    return parse_dbml(SCHEMA)


@cache
def _solution_text() -> str:
    paths = sorted(path for pattern in ("*.md", "*.yaml", "*.dbml") for path in ROOT.rglob(pattern))
    return " ".join("\n".join(path.read_text(encoding="utf-8") for path in paths).split())


def _leaf_signature(node: Condition) -> tuple[object, ...]:
    assert isinstance(node, Leaf)
    value = frozenset(node.value) if isinstance(node.value, list) else node.value
    return node.field, node.op, value


def _arm_signatures() -> list[set[tuple[object, ...]]]:
    rule = _bundle().mapping.list_validation["Platform"].when
    assert isinstance(rule, Group) and rule.kind == "all_of"
    arms: list[set[tuple[object, ...]]] = []
    for child in rule.children:
        assert isinstance(child, Group) and child.kind == "any_of"
        arms.append({_leaf_signature(leaf) for leaf in child.children})
    assert len(arms) == 4
    return arms


def test_obligation_verdicts_require_a_named_follow_up() -> None:
    arms = _arm_signatures()
    assert {
        ("DestinationVerdict", "not_in", frozenset(OBLIGATION_VERDICTS)),
        ("FollowUpRequired", "eq", True),
    } in arms
    assert {
        ("FollowUpRequired", "eq", False),
        ("FollowUpAction", "is_not_null", None),
    } in arms


def test_an_assessed_verdict_requires_a_date() -> None:
    assert {
        ("DestinationVerdict", "eq", "Not assessed"),
        ("AssessmentDate", "is_not_null", None),
    } in _arm_signatures()


def test_a_decommissioning_platform_is_not_a_destination() -> None:
    assert {
        ("LifecycleStatus", "not_in", frozenset({"Decommissioning"})),
        ("DestinationVerdict", "eq", "Not a destination"),
    } in _arm_signatures()


def test_bulk_export_view_names_the_predicate_it_uses() -> None:
    views = {view.title: view for view in _bundle().mapping.views["Platform"]}
    assert "No self-service bulk export route" in views
    assert "No bulk export route" not in views
    assert "No bulk export route" not in _solution_text()
    where = views["No self-service bulk export route"].where
    assert isinstance(where, Group)
    leaves = {_leaf_signature(leaf) for leaf in where.children}
    assert ("ExportMethods", "not_includes", "Self-service bulk export") in leaves


def test_default_and_blocked_view_contracts_match_their_titles() -> None:
    views = {view.title: view for view in _bundle().mapping.views["Platform"]}
    assert views["Current platform inventory"].default is True
    assert "Platforms in service" not in _solution_text()
    blocked = views["Cannot keep a record here"].where
    assert isinstance(blocked, Group)
    verdict = next(
        leaf for leaf in blocked.children
        if isinstance(leaf, Leaf) and leaf.field == "DestinationVerdict"
    )
    assert _leaf_signature(verdict) == (
        "DestinationVerdict",
        "in",
        frozenset({"Not a destination", *OBLIGATION_VERDICTS}),
    )


def test_follow_up_action_warns_against_identifiers() -> None:
    platform = next(table for table in _schema().tables if table.name == "Platform")
    column = next(column for column in platform.columns if column.name == "FollowUpAction")
    note = str(column.note).lower()
    assert "no patient or client identifiers" in note
    assert "categories" in note and "never examples" in note


def test_permission_scope_claims_carry_the_learn_source() -> None:
    assert _solution_text().count(PERMISSION_SCOPE_SOURCE) >= 4


def test_user_guidance_tracks_enum_couplings() -> None:
    text = _solution_text()
    message = _bundle().mapping.list_validation["Platform"].message
    assert all(verdict in message for verdict in OBLIGATION_VERDICTS)
    assert "`list_validation`" in text
    assert "`demo_items`" in text
    assert "five-place change" in text
    assert "A decommissioning platform must be Not a destination" in text


def test_conditional_demo_row_has_a_named_follow_up() -> None:
    row = next(
        item for item in _bundle().mapping.demo_items["Platform"]
        if item.key == "platform-rostering"
    )
    assert row.values["FollowUpRequired"] is True
    assert str(row.values["FollowUpAction"]).strip()


def test_threshold_position_is_a_bounded_inventory_contract() -> None:
    text = _solution_text()
    assert "one row per business platform" in text
    assert "if `RD_Platform` ever passes about 2,000 items" in text
    assert "these views are served because the list is small" in text
    assert "served past the list view threshold" not in text
    assert "an AND is served past" not in text
