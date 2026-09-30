# test/test_watched_uses.py
"""`watched_lists[].uses`: how the loader reads them and what the validator refuses.

Core reads a use's name, id, trigger and condition, keeps its `with:` block
untouched for the consumer, and checks only shape. Which use names exist is
not core's question, so no test here names one as unknown.
"""

from pathlib import Path

import pytest
from _packs import blocks, entities, write_mapping

from dbml_sharepoint.model.conditions import Group, Leaf, parse_condition
from dbml_sharepoint.model.errors import (
    MappingShapeError,
    MappingValueError,
    UnknownMappingKeyError,
)
from dbml_sharepoint.model.mapping_loader import load_mapping
from dbml_sharepoint.model.mapping_types import WatchedList, WatchUse

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
