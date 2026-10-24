"""The guards that type decoded JSON and YAML where it enters."""

import datetime as dt
from collections import UserDict
from collections.abc import Callable

import pytest

from dbml_sharepoint.jsonvalue import (
    JsonObject,
    as_json,
    as_json_object,
    as_object,
    ensure_object,
    int_at,
    is_json_value,
    is_object_list,
    is_text_keyed,
    loads_json,
    loads_object,
    object_at,
    opt_text,
    rows_at,
    text_at,
)


@pytest.mark.parametrize(
    "value",
    [None, "a", 1, 1.5, True, [], ["a", {"b": [None, 2]}], {"a": {"b": ["c"]}}],
)
def test_json_data_is_accepted_all_the_way_down(value: object) -> None:
    assert is_json_value(value)


@pytest.mark.parametrize(
    "value",
    [
        dt.date(2026, 1, 1), float("nan"), float("inf"), [float("-inf")], {"a": float("nan")},
        {1: "a"}, ["a", dt.date(2026, 1, 1)], {"a": {2: "b"}}, {"a"}, b"x",
    ],
)
def test_anything_else_is_refused_wherever_it_sits(value: object) -> None:
    assert not is_json_value(value)


def test_the_shallow_guards_check_only_the_container() -> None:
    assert is_text_keyed({"a": object()})
    assert not is_text_keyed({1: "a"})
    assert not is_text_keyed(["a"])
    assert is_object_list([object()])
    assert not is_object_list(("a",))


def test_as_json_object_returns_the_object_or_none() -> None:
    assert as_json_object({"a": [1]}) == {"a": [1]}
    assert as_json_object([1]) is None
    assert as_json_object({"a": dt.date(2026, 1, 1)}) is None


@pytest.mark.parametrize(
    "value",
    [
        b"x", bytearray(b"x"), range(3), ("a", "b"), UserDict({"a": 1}),
        ["a", ("b",)], {"a": range(2)},
    ],
    ids=[
        "bytes", "bytearray", "range", "tuple", "custom mapping", "nested tuple",
        "nested range",
    ],
)
def test_only_lists_and_dicts_are_json_containers(value: object) -> None:
    assert not is_json_value(value)
    assert as_json_object(value) is None


def test_as_json_copies_deeply_and_turns_sequences_into_lists() -> None:
    inner = ["b"]
    source = {"a": inner, "t": (1, None), "m": UserDict({"k": range(2)})}
    copied = as_json(source)
    assert copied == {"a": ["b"], "t": [1, None], "m": {"k": [0, 1]}}
    inner.append("c")
    assert copied == {"a": ["b"], "t": [1, None], "m": {"k": [0, 1]}}


def test_a_value_that_is_not_json_data_is_named() -> None:
    with pytest.raises(ValueError, match="spec holds a date, which is not JSON data"):
        as_json({"when": dt.date(2026, 1, 1)}, "spec")


@pytest.mark.parametrize("value", [b"x", bytearray(b"x"), {"a"}])
def test_bytes_and_sets_are_not_json_data(value: object) -> None:
    with pytest.raises(ValueError, match="payload holds a"):
        as_json(value, "payload")


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_as_json_refuses_a_non_finite_float(value: float) -> None:
    with pytest.raises(ValueError, match="payload"):
        as_json({"x": value}, "payload")


def test_as_json_refuses_a_non_text_key() -> None:
    with pytest.raises(ValueError, match="payload"):
        as_json({1: "a"}, "payload")


def test_as_object_raises_where_as_json_object_returns_none() -> None:
    assert as_json_object([1]) is None
    with pytest.raises(ValueError, match="must be a JSON object"):
        as_object([1])


def test_as_object_names_what_it_refuses() -> None:
    with pytest.raises(ValueError, match="thing must be a JSON object"):
        as_object([1], "thing")


def test_loads_json_reads_json_text_and_refuses_nan() -> None:
    assert loads_json(b'{"a": [1, 2.5, null]}') == {"a": [1, 2.5, None]}
    with pytest.raises(ValueError, match="JSON text holds nan, which has no JSON spelling"):
        loads_json("[NaN]")


def test_loads_object_refuses_anything_but_an_object() -> None:
    assert loads_object('{"a": 1}') == {"a": 1}
    with pytest.raises(ValueError, match="answer must be a JSON object"):
        loads_object("[1]", "answer")
    with pytest.raises(ValueError, match="answer"):
        loads_object('{"a": Infinity}', "answer")


@pytest.mark.parametrize(
    ("check", "key", "message"),
    [
        (text_at, "k", "'k' must be a string, got int"),
        (opt_text, "k", "'k' must be a string, got int"),
        (int_at, "s", "'s' must be a whole number, got 'x'"),
        (int_at, "b", "'b' must be a whole number, got bool"),
        (int_at, "f", "'f' must be a whole number, got float"),
        (object_at, "k", "'k' must be an object, got int"),
        (rows_at, "k", "'k' must be a list, got int"),
        (rows_at, "l", "'l' must hold objects, got int"),
        (ensure_object, "k", "'k' must be an object, got int"),
    ],
)
def test_a_value_of_the_wrong_type_is_refused_by_name(
    check: Callable[[JsonObject, str], object], key: str, message: str
) -> None:
    node: JsonObject = {"k": 1, "s": "x", "b": True, "f": 1.0, "l": [1]}
    with pytest.raises(ValueError, match=message):
        check(node, key)


def test_absent_values_read_as_their_defaults() -> None:
    node: JsonObject = {"n": None, "num": "7"}
    assert text_at(node, "n", "d") == "d"
    assert text_at(node, "absent") == ""
    assert opt_text(node, "n") is None
    assert int_at(node, "n", 3) == 3
    assert int_at(node, "num") == 7
    assert object_at(node, "n") == {}
    assert rows_at(node, "n") == []
    created = ensure_object(node, "made")
    assert node["made"] is created


def test_present_values_are_returned_as_they_are() -> None:
    row: JsonObject = {"id": 1}
    node: JsonObject = {"t": "x", "i": 4, "o": row, "r": [row]}
    assert text_at(node, "t") == "x"
    assert opt_text(node, "t") == "x"
    assert int_at(node, "i") == 4
    assert object_at(node, "o") is row
    assert rows_at(node, "r") == [row]
    assert ensure_object(node, "o") is row
