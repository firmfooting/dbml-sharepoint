# test/test_conditions.py
"""The shared condition grammar: parse, normalise, render."""

import pytest

from dbml_sharepoint.model.conditions import Group, Leaf, parse_condition


def test_bare_list_is_all_of() -> None:
    """views[].where has always been a flat ANDed list; that spelling must
    keep working, so a bare list is sugar for all_of."""
    condition = parse_condition([{"field": "Status", "op": "eq", "value": "Open"}], "ctx")
    assert condition == Group("all_of", (Leaf("Status", "eq", "Open"),))


def test_groups_nest() -> None:
    condition = parse_condition(
        {
            "any_of": [
                {"field": "A", "op": "eq", "value": 1},
                {"all_of": [{"field": "B", "op": "is_null"}]},
            ],
        },
        "ctx",
    )
    assert isinstance(condition, Group)
    assert condition.kind == "any_of"
    inner = condition.children[1]
    assert isinstance(inner, Group)
    assert inner.kind == "all_of"


def test_operand_transforms_parse() -> None:
    """`property` reaches into a person/lookup column, `measure` compares a
    derived scalar. Both leave op/value uniform so negation stays a flip."""
    persons = parse_condition(
        [{"field": "Owner", "property": "title", "op": "neq", "value": ""}], "ctx",
    )
    assert isinstance(persons, Group)
    leaf = persons.children[0]
    assert isinstance(leaf, Leaf)
    assert leaf.property == "title"

    lengths = parse_condition(
        [{"field": "Note", "measure": "length", "op": "gt", "value": 10}], "ctx",
    )
    assert isinstance(lengths, Group)
    measured = lengths.children[0]
    assert isinstance(measured, Leaf)
    assert measured.measure == "length"


@pytest.mark.parametrize(
    ("raw", "match"),
    [
        ({}, "exactly one of"),
        ({"all_of": [], "any_of": []}, "exactly one of"),
        ({"all_of": []}, "empty"),
        ({"all_of": "nope"}, "list"),
        ({"nope": []}, "exactly one of"),
        ([{"op": "eq", "value": 1}], "'field' is required"),
        ([{"field": "A"}], "'op' is required"),
        ("=TRUE", "mapping or a list"),
    ],
)
def test_structural_errors(raw: object, match: str) -> None:
    """Shape problems are load errors naming the offending context, as
    everywhere else in the mapping loader."""
    with pytest.raises(ValueError, match=match):
        parse_condition(raw, "ctx")


def test_unknown_leaf_key_is_rejected() -> None:
    """A typo in a leaf key must not be silently ignored — the loader's
    fail-open handling of unknown keys is a known defect elsewhere and is
    not repeated here."""
    with pytest.raises(ValueError, match="unknown key"):
        parse_condition([{"field": "A", "op": "eq", "vaule": 1}], "ctx")
