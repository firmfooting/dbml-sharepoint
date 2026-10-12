"""A decoded JSON document read with `[]`, checking the shape at every step.

Node output is JSON of a shape the test knows. Indexing it through `object`
needs a narrowing call per step, which buries the assertion in plumbing. This
view narrows as it is indexed: a missing key, a wrong container or a non-JSON
value raises at the step that is wrong, naming the value, instead of passing
on `undefined`.
"""

import json
from collections.abc import Iterator

from dbml_sharepoint.jsonvalue import JsonValue, is_json_value, is_object_list, is_text_keyed


class Json:
    """One JSON value. Equality compares the wrapped value; `[]` returns another view."""

    __slots__ = ("value",)

    def __init__(self, value: object) -> None:
        assert is_json_value(value), value
        self.value: JsonValue = value

    @staticmethod
    def loads(text: str) -> "Json":
        return Json(json.loads(text))

    def __getitem__(self, key: str | int | slice) -> "Json":
        value = self.value
        if isinstance(key, str):
            assert isinstance(value, dict), f"{key!r} read from {value!r}"
            assert key in value, f"{key!r} missing from {value!r}"
            return Json(value[key])
        assert isinstance(value, list), f"{key!r} read from {value!r}"
        return Json(value[key])

    def get(self, key: str, default: JsonValue = None) -> "Json":
        assert isinstance(self.value, dict), f"{key!r} read from {self.value!r}"
        return Json(self.value.get(key, default))

    def keys(self) -> list[str]:
        assert isinstance(self.value, dict), self.value
        return list(self.value)

    def values(self) -> list["Json"]:
        assert isinstance(self.value, dict), self.value
        return [Json(item) for item in self.value.values()]

    def items(self) -> list[tuple[str, "Json"]]:
        assert isinstance(self.value, dict), self.value
        return [(key, Json(item)) for key, item in self.value.items()]

    def __iter__(self) -> Iterator["Json"]:
        """Elements of an array, keys of an object, as `for x in value` would."""
        value = self.value
        assert is_object_list(value) or is_text_keyed(value), value
        return iter([Json(item) for item in value])

    def __len__(self) -> int:
        value = self.value
        assert isinstance(value, str) or is_object_list(value) or is_text_keyed(value), value
        return len(value)

    def __contains__(self, item: object) -> bool:
        needle = item.value if isinstance(item, Json) else item
        if isinstance(self.value, str):
            assert isinstance(needle, str), needle
            return needle in self.value
        value = self.value
        assert is_object_list(value) or is_text_keyed(value), value
        return needle in value

    def __bool__(self) -> bool:
        return bool(self.value)

    def __eq__(self, other: object) -> bool:
        return self.value == (other.value if isinstance(other, Json) else other)

    def __hash__(self) -> int:
        container = is_object_list(self.value) or is_text_keyed(self.value)
        assert not container, "only a scalar view is hashable"
        return hash(self.value)

    def __str__(self) -> str:
        return str(self.value)

    def __repr__(self) -> str:
        return f"Json({self.value!r})"

    @property
    def is_none(self) -> bool:
        return self.value is None

    @property
    def text(self) -> str:
        assert isinstance(self.value, str), self.value
        return self.value

    @property
    def number(self) -> int:
        assert isinstance(self.value, int) and not isinstance(self.value, bool), self.value
        return self.value

    @property
    def rows(self) -> list["Json"]:
        return list(self)

    def __lt__(self, other: "Json | int | float | str") -> bool:
        return self._ordered(other) < 0

    def __le__(self, other: "Json | int | float | str") -> bool:
        return self._ordered(other) <= 0

    def __gt__(self, other: "Json | int | float | str") -> bool:
        return self._ordered(other) > 0

    def __ge__(self, other: "Json | int | float | str") -> bool:
        return self._ordered(other) >= 0

    def _ordered(self, other: "Json | int | float | str") -> int:
        """Sign of self - other for two numbers or two strings, asserting both are one kind."""
        right = other.value if isinstance(other, Json) else other
        left = self.value
        if isinstance(left, str):
            assert isinstance(right, str), (left, right)
            return (left > right) - (left < right)
        assert isinstance(left, int | float) and not isinstance(left, bool), left
        assert isinstance(right, int | float) and not isinstance(right, bool), right
        return (left > right) - (left < right)

    def __add__(self, other: "Json | str") -> str:
        return self.text + (other.text if isinstance(other, Json) else other)

    def __radd__(self, other: str) -> str:
        return other + self.text

    def startswith(self, prefix: str | tuple[str, ...]) -> bool:
        return self.text.startswith(prefix)

    def endswith(self, suffix: str | tuple[str, ...]) -> bool:
        return self.text.endswith(suffix)

    def count(self, sub: str) -> int:
        return self.text.count(sub)

    def split(self, sep: str, maxsplit: int = -1) -> list[str]:
        return self.text.split(sep, maxsplit)

    def splitlines(self) -> list[str]:
        return self.text.splitlines()

    def removeprefix(self, prefix: str) -> str:
        return self.text.removeprefix(prefix)

    def removesuffix(self, suffix: str) -> str:
        return self.text.removesuffix(suffix)

    def lower(self) -> str:
        return self.text.lower()

    @property
    def strings(self) -> list[str]:
        return [item.text for item in self]

    def dumps(self) -> str:
        return json.dumps(self.value)

    @property
    def is_object(self) -> bool:
        return isinstance(self.value, dict)

    def index(self, item: "Json") -> int:
        return self.rows.index(item)


def _unwrap(value: object) -> JsonValue:
    assert isinstance(value, Json), value
    return value.value


def dumps(value: object) -> str:
    """`json.dumps` for a structure that holds views, such as a dict of result rows."""
    return json.dumps(value, default=_unwrap)
