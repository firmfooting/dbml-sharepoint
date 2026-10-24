"""The shape of decoded JSON and YAML, and guards that type it where it enters."""

import json
import math
from collections.abc import Mapping, Sequence
from typing import TypeGuard

# Concrete containers only: a tuple, bytes, range or custom mapping is not decoded JSON.
type JsonValue = str | int | float | bool | list[JsonValue] | dict[str, JsonValue] | None
type JsonObject = dict[str, JsonValue]
# For parameters: read-only and covariant, so a ``dict[str, str]`` is accepted too.
type JsonMap = Mapping[str, JsonValue]


def is_text_keyed(value: object) -> TypeGuard[dict[str, object]]:
    """Whether ``value`` is a dict whose keys are all strings (its values are not checked)."""
    return isinstance(value, dict) and all(isinstance(key, str) for key in value)


def is_object_list(value: object) -> TypeGuard[list[object]]:
    """Whether ``value`` is a list (its items are not checked)."""
    return isinstance(value, list)


def is_json_value(value: object) -> TypeGuard[JsonValue]:
    """Whether ``value`` is JSON all the way down, with string keys in every object."""
    if isinstance(value, float):
        return math.isfinite(value)  # NaN and the infinities have no JSON spelling
    if value is None or isinstance(value, str | bool | int):
        return True
    if is_object_list(value):
        return all(is_json_value(item) for item in value)
    if is_text_keyed(value):
        return all(is_json_value(item) for item in value.values())
    return False


def as_json_object(value: object) -> dict[str, JsonValue] | None:
    """``value`` when it is a JSON object, else None."""
    if is_json_value(value) and isinstance(value, dict):
        return value
    return None


def as_json(value: object, what: str = "value") -> JsonValue:
    """A deep copy of ``value`` as JSON data, sequences as lists; anything else is refused."""
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{what} holds {value!r}, which has no JSON spelling")
    if value is None or isinstance(value, str | bool | int | float):
        return value
    if isinstance(value, Mapping):
        items: Mapping[object, object] = value
        copied: JsonObject = {}
        for key, item in items.items():
            if not isinstance(key, str):
                raise ValueError(f"{what} has the key {key!r}, which is not text")
            copied[key] = as_json(item, what)
        return copied
    # Bytes are a sequence of ints to Python, but not a JSON array.
    if isinstance(value, Sequence) and not isinstance(value, bytes | bytearray | memoryview):
        elements: Sequence[object] = value
        return [as_json(item, what) for item in elements]
    raise ValueError(f"{what} holds a {type(value).__name__}, which is not JSON data")


def loads_json(text: str | bytes) -> JsonValue:
    """``json.loads`` through ``as_json``, so the NaN and Infinity it accepts are refused."""
    return as_json(json.loads(text), "JSON text")


def loads_object(text: str | bytes, what: str = "value") -> JsonObject:
    """``json.loads`` refusing anything but a JSON object."""
    return as_object(json.loads(text), what)


def as_object(value: object, what: str = "value") -> JsonObject:
    """A deep copy of ``value`` as a JSON object, raising where ``as_json_object`` returns None."""
    data = as_json(value, what)
    if not isinstance(data, dict):
        raise ValueError(f"{what} must be a JSON object")
    return data


def text_at(node: JsonMap, key: str, default: str = "") -> str:
    """``node[key]`` as a string; ``default`` when absent or null, an error for another type."""
    value = node.get(key)
    if value is None:
        return default
    if not isinstance(value, str):
        raise ValueError(f"{key!r} must be a string, got {type(value).__name__}")
    return value


def opt_text(node: JsonMap, key: str) -> str | None:
    """``node[key]`` as a string, None when absent or null."""
    return None if node.get(key) is None else text_at(node, key)


def int_at(node: JsonMap, key: str, default: int = 0) -> int:
    """``node[key]`` as an int (numeric text read, bools refused); ``default`` if absent or null."""
    value = node.get(key)
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int | str):
        raise ValueError(f"{key!r} must be a whole number, got {type(value).__name__}")
    try:
        return int(value)
    except ValueError:
        raise ValueError(f"{key!r} must be a whole number, got {value!r}") from None


def object_at(node: JsonMap, key: str) -> JsonObject:
    """The object under ``node[key]``, empty when absent or null, an error for another type."""
    value = node.get(key)
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{key!r} must be an object, got {type(value).__name__}")
    return value


def rows_at(node: JsonMap, key: str) -> list[JsonObject]:
    """The list of objects under ``node[key]``, empty when absent or null."""
    value = node.get(key)
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{key!r} must be a list, got {type(value).__name__}")
    rows: list[JsonObject] = []
    for row in value:
        if not isinstance(row, dict):
            raise ValueError(f"{key!r} must hold objects, got {type(row).__name__}")
        rows.append(row)
    return rows


def ensure_object(parent: JsonObject, key: str) -> JsonObject:
    """The live object under ``parent[key]``, created empty when the key is absent or null."""
    if parent.get(key) is None:
        parent[key] = {}
    return object_at(parent, key)
