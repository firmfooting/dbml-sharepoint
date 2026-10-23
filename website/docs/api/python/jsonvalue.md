---
title: jsonvalue
sidebar_position: 57
---

# `dbml_sharepoint.jsonvalue`

*the shape of decoded JSON and the guards that type it*

The shape of decoded JSON and YAML, and guards that type it where it enters.

### `is_text_keyed`

```python
def is_text_keyed(value: object) -> TypeGuard[dict[str, object]]
```

Whether ``value`` is a dict whose keys are all strings (its values are not checked).

### `is_object_list`

```python
def is_object_list(value: object) -> TypeGuard[list[object]]
```

Whether ``value`` is a list (its items are not checked).

### `is_json_value`

```python
def is_json_value(value: object) -> TypeGuard[JsonValue]
```

Whether ``value`` is JSON all the way down, with string keys in every object.

### `as_json_object`

```python
def as_json_object(value: object) -> dict[str, JsonValue] | None
```

``value`` when it is a JSON object, else None.

