"""Narrowing helpers for tests that read a decoded YAML document."""

from dbml_sharepoint.jsonvalue import is_object_list, is_text_keyed


def as_dict(value: object) -> dict[str, object]:
    assert is_text_keyed(value), value
    return value


def as_list(value: object) -> list[object]:
    assert is_object_list(value), value
    return value


def as_str(value: object) -> str:
    assert isinstance(value, str), value
    return value
