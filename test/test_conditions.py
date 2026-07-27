# test/test_conditions.py
"""The shared condition grammar: parse, normalise, render."""

import pytest

from dbml_sharepoint.analysis.conditions import NEGATION, measure_tree, normalise
from dbml_sharepoint.model.conditions import Condition, Group, Leaf, parse_condition


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


# === Normalisation ==========================================================

def test_every_operator_has_an_exact_negation() -> None:
    """De Morgan is what lets one grammar serve a CAML target with no
    group-level NOT: negation is pushed to the leaves and each operator
    flips. An operator added without an inverse would silently break
    none_of, so the involution is asserted rather than assumed."""
    for op, negated in NEGATION.items():
        assert NEGATION[negated] == op, f"{op}/{negated} is not an involution"


def test_none_of_becomes_negated_leaves() -> None:
    condition = parse_condition({"none_of": [{"field": "A", "op": "eq", "value": 1}]}, "ctx")
    assert normalise(condition) == Group("all_of", (Leaf("A", "neq", 1),))


def test_nested_negation_flips_group_kind() -> None:
    """not(any_of[X, Y]) is all_of[not X, not Y]."""
    condition = parse_condition(
        {
            "none_of": [
                {
                    "any_of": [
                        {"field": "A", "op": "eq", "value": 1},
                        {"field": "B", "op": "gt", "value": 2},
                    ],
                },
            ],
        },
        "ctx",
    )
    assert normalise(condition) == Group(
        "all_of", (Group("all_of", (Leaf("A", "neq", 1), Leaf("B", "leq", 2))),),
    )


def test_double_negation_restores_the_original() -> None:
    """none_of[none_of[A]] is A. A normaliser that does not round-trip here
    is flipping something it should not."""
    condition = parse_condition(
        {"none_of": [{"none_of": [{"field": "A", "op": "eq", "value": 1}]}]}, "ctx",
    )
    assert normalise(condition) == Group("all_of", (Group("any_of", (Leaf("A", "eq", 1),)),))


def _kinds(node: Condition) -> list[str]:
    if isinstance(node, Group):
        return [node.kind, *[k for child in node.children for k in _kinds(child)]]
    return []


def test_normalise_leaves_no_none_of() -> None:
    """The renderers' contract: they never meet a negated group, which is
    why CAML — which cannot express one — is a viable target."""
    condition = parse_condition(
        {
            "any_of": [
                {"none_of": [{"field": "A", "op": "is_null"}]},
                {"field": "B", "op": "eq", "value": 1},
            ],
        },
        "ctx",
    )
    assert "none_of" not in _kinds(normalise(condition))


def test_normalise_preserves_operand_transforms() -> None:
    condition = parse_condition(
        {"none_of": [{"field": "Owner", "property": "title", "op": "eq", "value": "x"}]}, "ctx",
    )
    normalised = normalise(condition)
    assert isinstance(normalised, Group)
    leaf = normalised.children[0]
    assert isinstance(leaf, Leaf)
    assert leaf.property == "title"
    assert leaf.op == "neq"


def test_measure_tree_counts_depth_and_leaves() -> None:
    condition = parse_condition(
        {
            "any_of": [
                {"field": "A", "op": "eq", "value": 1},
                {
                    "all_of": [
                        {"field": "B", "op": "eq", "value": 2},
                        {"field": "C", "op": "eq", "value": 3},
                    ],
                },
            ],
        },
        "ctx",
    )
    assert measure_tree(condition) == (2, 3)
