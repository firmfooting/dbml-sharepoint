"""The guards that type decoded JSON and YAML where it enters."""

import datetime as dt
from collections import UserDict

import pytest

from dbml_sharepoint.jsonvalue import (
    as_json_object,
    is_json_value,
    is_object_list,
    is_text_keyed,
)


@pytest.mark.parametrize(
    "value",
    [None, "a", 1, 1.5, True, [], ["a", {"b": [None, 2]}], {"a": {"b": ["c"]}}],
)
def test_json_data_is_accepted_all_the_way_down(value: object) -> None:
    assert is_json_value(value)


@pytest.mark.parametrize(
    "value",
    [dt.date(2026, 1, 1), {1: "a"}, ["a", dt.date(2026, 1, 1)], {"a": {2: "b"}}, {"a"}, b"x"],
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
