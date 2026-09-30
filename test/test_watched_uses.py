# test/test_watched_uses.py
"""`watched_lists[].uses`: how the loader reads them and what the validator refuses.

Core reads a use's name, id, trigger and condition, keeps its `with:` block
untouched for the consumer, and checks their shape and each `when` against the
schema. Which use names exist is not core's question, so no test here names
one as unknown.
"""

from pathlib import Path

import pytest
from _findings import codes, none_of, only
from _model import bundle as make_bundle
from _model import column as make_column
from _model import enum as make_enum
from _model import schema as make_schema
from _model import table as make_table
from _packs import blocks, entities, write_mapping

from dbml_sharepoint.analysis.condition_rendering import CAML
from dbml_sharepoint.analysis.conditions import condition_findings
from dbml_sharepoint.analysis.findings import Finding, FindingCode, Location, Section
from dbml_sharepoint.analysis.validator import validate_against_mapping
from dbml_sharepoint.model.conditions import Group, Leaf, parse_condition
from dbml_sharepoint.model.errors import (
    MappingShapeError,
    MappingValueError,
    UnknownMappingKeyError,
)
from dbml_sharepoint.model.mapping_loader import load_mapping
from dbml_sharepoint.model.mapping_types import WatchedList, WatchOn, WatchUse

# --- loading -----------------------------------------------------------------


def _load(tmp_path: Path, watched: str) -> tuple[WatchUse, ...]:
    write_mapping(tmp_path, blocks(entities("Project"), watched))
    return load_mapping(tmp_path / "m.yaml").mapping.watched_lists[0].uses


def _refused(tmp_path: Path, watched: str, error: type[Exception], match: str) -> None:
    write_mapping(tmp_path, blocks(entities("Project"), watched))
    with pytest.raises(error, match=match):
        load_mapping(tmp_path / "m.yaml")


def test_a_bare_name_and_a_mapping_both_load(tmp_path: Path) -> None:
    uses = _load(tmp_path, """
        watched_lists:
          - entity: Project
            column: Status
            uses:
              - history
              - alert:
                  id: closed
                  on: enter
                  when: { op: eq, value: Closed }
                  with: { to: owner, note: { nested: [1, 2] } }
    """)

    assert uses == (
        WatchUse(name="history"),
        WatchUse(
            name="alert",
            id="closed",
            on="enter",
            when=Leaf(field="Status", op="eq", value="Closed"),
            settings={"to": "owner", "note": {"nested": [1, 2]}},
        ),
    )


def test_an_entry_with_no_uses_has_none(tmp_path: Path) -> None:
    uses = _load(tmp_path, """
        watched_lists:
          - { entity: Project, column: Status }
    """)

    assert uses == ()


def test_a_use_with_no_settings_takes_the_defaults(tmp_path: Path) -> None:
    uses = _load(tmp_path, """
        watched_lists:
          - entity: Project
            column: Status
            uses:
              - alert:
    """)

    assert uses == (WatchUse(name="alert"),)
    assert uses[0].on == "change"
    assert uses[0].settings == {}


def test_a_use_and_its_entry_stay_hashable() -> None:
    use = WatchUse("alert", id="closed", on="enter", when=Leaf("Status", "eq", "Closed"),
                   settings={"notify": ["Owner"]})
    entry = WatchedList(entity="Project", column="Status", uses=(use,))

    unset = WatchUse("alert", id="closed", on="enter", when=Leaf("Status", "eq", "Closed"))
    assert hash(use) == hash(unset)
    assert {entry, WatchedList(entity="Project", column="Status", uses=(use,))} == {entry}


def test_every_leaf_without_a_field_compares_the_watched_column(tmp_path: Path) -> None:
    uses = _load(tmp_path, """
        watched_lists:
          - entity: Project
            column: Status
            uses:
              - alert:
                  on: leave
                  when:
                    any_of:
                      - { op: eq, value: Closed }
                      - { field: Owner, op: is_null }
    """)

    assert uses[0].when == Group("any_of", (
        Leaf(field="Status", op="eq", value="Closed"),
        Leaf(field="Owner", op="is_null"),
    ))


def test_a_blank_field_is_refused_rather_than_defaulted(tmp_path: Path) -> None:
    _refused(tmp_path, """
        watched_lists:
          - entity: Project
            column: Status
            uses:
              - alert: { on: enter, when: { field: , op: eq, value: Closed } }
    """, MappingShapeError, r"watched_lists\[0\]\.uses\[0\]\.when: 'field' is required")


def test_a_condition_elsewhere_still_needs_its_field() -> None:
    with pytest.raises(MappingShapeError, match="'field' is required"):
        parse_condition({"op": "eq", "value": "Closed"}, "views[Project][0].where")


@pytest.mark.parametrize(("uses", "error", "match"), [
    pytest.param("- alert: { id: a, colour: red }", UnknownMappingKeyError,
                 r"watched_lists\[0\]\.uses\[0\]: unknown key", id="unknown-key"),
    pytest.param("- { alert: {}, history: {} }", MappingShapeError,
                 r"watched_lists\[0\]\.uses\[0\]: expected a use name", id="two-names"),
    pytest.param("- 3", MappingShapeError,
                 r"watched_lists\[0\]\.uses\[0\]: expected a use name", id="number"),
    pytest.param("- 1: {}", MappingShapeError,
                 r"watched_lists\[0\]\.uses\[0\]: key 1 is not text", id="name-not-text"),
    pytest.param("- alert: { on: later }", MappingValueError,
                 r"watched_lists\[0\]\.uses\[0\]\.on must be one of", id="on"),
    pytest.param("- alert: { id: [a] }", MappingShapeError,
                 r"watched_lists\[0\]\.uses\[0\]\.id must be a string", id="id"),
    pytest.param("- alert: 3", MappingShapeError,
                 r"watched_lists\[0\]\.uses\[0\]: expected a mapping, got int", id="settings"),
    pytest.param("- alert: { with: [a] }", MappingShapeError,
                 r"watched_lists\[0\]\.uses\[0\]\.with: expected a mapping", id="with"),
    pytest.param("- alert: { when: 3 }", MappingShapeError,
                 r"watched_lists\[0\]\.uses\[0\]\.when: expected a mapping", id="when"),
])
def test_a_malformed_use_is_refused_where_it_is(
        tmp_path: Path, uses: str, error: type[Exception], match: str) -> None:
    _refused(tmp_path, f"""
        watched_lists:
          - entity: Project
            column: Status
            uses:
              {uses}
    """, error, match)


def test_uses_that_are_not_a_list_are_refused(tmp_path: Path) -> None:
    _refused(tmp_path, """
        watched_lists:
          - { entity: Project, column: Status, uses: history }
    """, MappingShapeError, r"watched_lists\[0\]\.uses: expected a list")


# --- validating --------------------------------------------------------------

SCHEMA = make_schema(
    make_table(
        "Project",
        make_column("Title", required=True),
        make_column("Status", "project_status"),
        make_column("Owner", "person"),
        make_column("Note"),
        note="Projects.",
    ),
    make_table("Task", make_column("Title", required=True), note="Tasks."),
    enums=[make_enum("project_status", "Open", "Closed")],
)


def _validate(*watched: WatchedList) -> list[Finding]:
    return validate_against_mapping(
        SCHEMA, make_bundle(entities=["Project", "Task"], watched_lists=list(watched)),
    )


def _on_status(*uses: WatchUse) -> WatchedList:
    return WatchedList(entity="Project", column="Status", uses=uses)


@pytest.mark.parametrize("name", ["history", "a", "owner-alert-2"])
def test_a_well_formed_use_name_is_accepted(name: str) -> None:
    none_of(_validate(_on_status(WatchUse(name))), FindingCode.WATCH_USE_NAME_INVALID)


@pytest.mark.parametrize("name", ["History", "2nd", "-alert", "owner_alert", ""])
def test_a_malformed_use_name_is_refused(name: str) -> None:
    finding = only(_validate(_on_status(WatchUse(name))), FindingCode.WATCH_USE_NAME_INVALID)

    assert finding.location == Location(Section.WATCHED_LISTS, sub="[0].uses[0]")
    assert repr(name) in finding.message


@pytest.mark.parametrize("use_id", ["Closed", "2nd", "-a", "owner_alert", ""])
def test_a_malformed_use_id_is_refused(use_id: str) -> None:
    findings = _validate(_on_status(WatchUse("alert", id=use_id)))

    finding = only(findings, FindingCode.WATCH_USE_ID_INVALID)

    assert finding.location == Location(Section.WATCHED_LISTS, sub="[0].uses[0]")
    assert finding.message == (
        f"watched_lists[0].uses[0]: id {use_id!r} must be lowercase letters, digits and hyphens, "
        "starting with a letter."
    )


def test_a_well_formed_use_id_is_accepted() -> None:
    findings = _validate(_on_status(WatchUse("alert", id="owner-closed-2")))

    none_of(findings, FindingCode.WATCH_USE_ID_INVALID)


def test_a_use_name_is_checked_on_an_unknown_entity_too() -> None:
    findings = _validate(WatchedList(entity="Nowhere", column="Status", uses=(WatchUse("X"),)))

    assert {FindingCode.UNKNOWN_ENTITY, FindingCode.WATCH_USE_NAME_INVALID} <= codes(findings)


@pytest.mark.parametrize("on", ["enter", "leave"])
def test_enter_and_leave_need_a_when(on: WatchOn) -> None:
    use = WatchUse("alert", on=on)

    finding = only(_validate(_on_status(use)), FindingCode.WATCH_USE_WHEN_REQUIRED)

    assert finding.message == (
        f"watched_lists[0].uses[0]: 'on: {on}' needs a 'when' saying which values of "
        f"'Status' it {on}s."
    )


def test_change_needs_no_when() -> None:
    none_of(_validate(_on_status(WatchUse("history"))), FindingCode.WATCH_USE_WHEN_REQUIRED)


def test_change_with_a_when_is_accepted() -> None:
    use = WatchUse("alert", when=Leaf("Status", "eq", "Closed"))

    findings = _validate(_on_status(use))

    assert not [f for f in findings
                if f.location is not None and f.location.section is Section.WATCHED_LISTS]


def test_a_name_repeated_on_one_entity_needs_an_id_on_each_use() -> None:
    findings = _validate(
        _on_status(WatchUse("alert")),
        WatchedList(entity="Project", column="Owner", uses=(WatchUse("alert", id="owner"),)),
    )

    finding = only(findings, FindingCode.WATCH_USE_REPEATED_WITHOUT_ID)
    assert finding.location == Location(Section.WATCHED_LISTS, sub="[0].uses[0]")
    assert "'alert' is used 2 times on Project" in finding.message


def test_a_name_repeated_on_two_entities_needs_no_id() -> None:
    findings = _validate(
        _on_status(WatchUse("alert")),
        WatchedList(entity="Task", column="Title", uses=(WatchUse("alert"),)),
    )

    none_of(findings, FindingCode.WATCH_USE_REPEATED_WITHOUT_ID)


def test_a_repeated_name_with_an_id_on_every_use_is_accepted() -> None:
    findings = _validate(_on_status(WatchUse("alert", id="a"), WatchUse("alert", id="b")))

    none_of(findings, FindingCode.WATCH_USE_REPEATED_WITHOUT_ID)
    none_of(findings, FindingCode.WATCH_USE_ID_DUPLICATE)


def test_an_id_used_twice_on_one_entity_is_refused_at_the_second_use() -> None:
    findings = _validate(
        _on_status(WatchUse("alert", id="same")),
        WatchedList(entity="Project", column="Owner", uses=(WatchUse("digest", id="same"),)),
    )

    finding = only(findings, FindingCode.WATCH_USE_ID_DUPLICATE)
    assert finding.location == Location(Section.WATCHED_LISTS, sub="[1].uses[0]")
    assert finding.message == (
        "watched_lists[1].uses[0]: id 'same' is already used on Project by "
        "watched_lists[0].uses[0]."
    )


def test_an_id_on_two_entities_is_accepted() -> None:
    findings = _validate(
        _on_status(WatchUse("alert", id="same")),
        WatchedList(entity="Task", column="Title", uses=(WatchUse("alert", id="same"),)),
    )

    none_of(findings, FindingCode.WATCH_USE_ID_DUPLICATE)


def test_a_sound_when_raises_nothing() -> None:
    use = WatchUse("alert", on="enter", when=Leaf("Status", "eq", "Closed"))

    findings = _validate(_on_status(use))

    assert not [f for f in findings
                if f.location is not None and f.location.section is Section.WATCHED_LISTS]


@pytest.mark.parametrize(("when", "code", "sub"), [
    pytest.param(Leaf("Nope", "eq", "x"), FindingCode.CONDITION_FIELD_NOT_RENDERED,
                 "[0].uses[0].when.Nope", id="field"),
    pytest.param(Leaf("Status", "equals", "Closed"), FindingCode.CONDITION_OPERATOR_UNKNOWN,
                 "[0].uses[0].when.Status", id="operator"),
    pytest.param(Leaf("Status", "eq", "Closd"), FindingCode.CONDITION_CHOICE_MEMBER_UNKNOWN,
                 "[0].uses[0].when.Status", id="choice-member"),
])
def test_a_when_is_judged_against_the_schema(when: Leaf, code: FindingCode, sub: str) -> None:
    finding = only(_validate(_on_status(WatchUse("alert", on="enter", when=when))), code)

    assert finding.location == Location(Section.WATCHED_LISTS, sub=sub)


def test_a_when_on_an_unrendered_column_is_left_to_the_column_finding() -> None:
    use = WatchUse("alert", on="enter", when=Leaf("Nope", "eq", "x"))

    findings = _validate(WatchedList(entity="Project", column="Nope", uses=(use,)))

    only(findings, FindingCode.WATCHED_COLUMN_NOT_RENDERED)
    none_of(findings, FindingCode.CONDITION_FIELD_NOT_RENDERED)


def _judged(target: str | None) -> list[Finding]:
    return condition_findings(
        Leaf("Note", "not_contains", "draft"),
        target=target,
        rendered={"Note"},
        types={"Note": "nvarchar"},
        lookups=set(),
        enum_members={},
        at=Location(Section.WATCHED_LISTS, sub="[0].uses[0].when"),
    )


def test_a_condition_nothing_renders_is_not_refused_for_an_operator_one_target_lacks() -> None:
    assert _judged(None) == []
    assert _judged(CAML) != []
