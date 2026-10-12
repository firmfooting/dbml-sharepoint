"""The shape of decoded JSON and YAML, and guards that type it where it enters."""

from typing import TypeGuard

# Concrete containers only: a tuple, bytes, range or custom mapping is not decoded JSON.
type JsonValue = str | int | float | bool | list[JsonValue] | dict[str, JsonValue] | None
type JsonObject = dict[str, JsonValue]


def is_text_keyed(value: object) -> TypeGuard[dict[str, object]]:
    """Whether ``value`` is a dict whose keys are all strings (its values are not checked)."""
    return isinstance(value, dict) and all(isinstance(key, str) for key in value)


def is_object_list(value: object) -> TypeGuard[list[object]]:
    """Whether ``value`` is a list (its items are not checked)."""
    return isinstance(value, list)


def is_json_value(value: object) -> TypeGuard[JsonValue]:
    """Whether ``value`` is JSON all the way down, with string keys in every object."""
    if value is None or isinstance(value, str | bool | int | float):
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
