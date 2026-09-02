# test/test_save_rules.py
"""Where a save rule against the clock is enforced.

MEASURED 2026-09-02 on a live tenant in AUS Eastern: TODAY() and NOW() in a
validation formula ran 16 to 20 hours behind the site, so `=[D]<=TODAY()`
refused the current date until late afternoon. In a LIST validation formula
`[Modified]` is the instant of the save being validated, in site-local time,
on create and on update, and `[Created]` is set on a new item. A COLUMN
validation formula may reference only its own column, so a column rule
against the clock has to move to the list to be exact.
"""
from _model import mapping as make_mapping

from dbml_sharepoint.analysis.save_rules import (
    compares_with_the_clock,
    effective_list_validation,
    hoisted_columns,
)
from dbml_sharepoint.model.conditions import Group, Leaf
from dbml_sharepoint.model.mapping_types import (
    ColumnValidation,
    EntitySection,
    ListValidation,
)

TYPES = {"Due": "date", "OccurredAt": "datetime", "Note": "nvarchar", "Status": "nvarchar"}


def _rule(field: str, op: str, value: object, message: str = "m") -> ColumnValidation:
    return ColumnValidation(when=Leaf(field=field, op=op, value=value), message=message)


def test_a_date_compared_with_today_or_now_is_a_clock_comparison() -> None:
    assert compares_with_the_clock(Leaf(field="Due", op="leq", value="today"), TYPES)
    assert compares_with_the_clock(Leaf(field="Due", op="leq", value="today+365"), TYPES)
    assert compares_with_the_clock(Leaf(field="OccurredAt", op="leq", value="now"), TYPES)
    # The literal word on a text column is a word.
    assert not compares_with_the_clock(Leaf(field="Note", op="eq", value="today"), TYPES)
    # A date literal is not the clock.
    assert not compares_with_the_clock(Leaf(field="Due", op="leq", value="2026-09-02"), TYPES)
    # Anywhere in a tree counts.
    tree = Group("all_of", (Leaf(field="Status", op="neq", value="Done"),
                            Leaf(field="Due", op="lt", value="today-42")))
    assert compares_with_the_clock(tree, TYPES)


def test_only_clock_rules_are_hoisted_in_declaration_order() -> None:
    section = EntitySection(columns={
        "Note": _rule("Note", "neq", "forbidden"),
        "OccurredAt": _rule("OccurredAt", "leq", "now"),
        "Due": _rule("Due", "leq", "today"),
    })
    assert [name for name, _ in hoisted_columns(section, TYPES)] == ["OccurredAt", "Due"]
    assert hoisted_columns(None, TYPES) == []


def test_without_a_clock_rule_the_declared_list_rule_is_returned_unchanged() -> None:
    declared = ListValidation(when=Leaf(field="Status", op="neq", value="x"), message="Keep.")
    mapping = make_mapping(entities=["Risk"], list_validation={"Risk": declared})
    assert effective_list_validation(mapping, "Risk", TYPES) is declared
    assert effective_list_validation(make_mapping(entities=["Risk"]), "Risk", TYPES) is None


def test_a_hoisted_rule_is_guarded_for_a_blank_and_keeps_its_message() -> None:
    """A column rule never fires on a blank value; the guard keeps that once
    the rule sits on the list, where every save evaluates it."""
    rule = _rule("Due", "leq", "today", "Not in the future.")
    mapping = make_mapping(
        entities=["Risk"],
        column_validation={"Risk": EntitySection(columns={"Due": rule})},
    )
    effective = effective_list_validation(mapping, "Risk", TYPES)
    assert effective is not None
    assert effective.message == "Not in the future."
    assert effective.when == Group("all_of", (
        Group("any_of", (Leaf(field="Due", op="is_null"), rule.when)),
    ))


def test_hoisted_rules_join_the_declared_list_rule_and_its_message_first() -> None:
    declared = ListValidation(
        when=Leaf(field="Status", op="neq", value="Done"), message="Done needs a date.",
    )
    due = _rule("Due", "leq", "today", "Not in the future.")
    occurred = _rule("OccurredAt", "leq", "now", "Not after now.")
    mapping = make_mapping(
        entities=["Risk"],
        list_validation={"Risk": declared},
        column_validation={"Risk": EntitySection(columns={"Due": due, "OccurredAt": occurred})},
    )
    effective = effective_list_validation(mapping, "Risk", TYPES)
    assert effective is not None
    assert effective.when == Group("all_of", (
        declared.when,
        Group("any_of", (Leaf(field="Due", op="is_null"), due.when)),
        Group("any_of", (Leaf(field="OccurredAt", op="is_null"), occurred.when)),
    ))
    assert effective.message == "Done needs a date. Not in the future. Not after now."
