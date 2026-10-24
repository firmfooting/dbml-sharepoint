---
title: jsonvalue
sidebar_position: 58
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

### `as_json`

```python
def as_json(value: object, what: str = 'value') -> JsonValue
```

A deep copy of ``value`` as JSON data, sequences as lists; anything else is refused.

### `loads_json`

```python
def loads_json(text: str | bytes) -> JsonValue
```

``json.loads`` through ``as_json``, so the NaN and Infinity it accepts are refused.

### `loads_object`

```python
def loads_object(text: str | bytes, what: str = 'value') -> JsonObject
```

``json.loads`` refusing anything but a JSON object.

### `as_object`

```python
def as_object(value: object, what: str = 'value') -> JsonObject
```

A deep copy of ``value`` as a JSON object, raising where ``as_json_object`` returns None.

### `text_at`

```python
def text_at(node: JsonMap, key: str, default: str = '') -> str
```

``node[key]`` as a string; ``default`` when absent or null, an error for another type.

### `opt_text`

```python
def opt_text(node: JsonMap, key: str) -> str | None
```

``node[key]`` as a string, None when absent or null.

### `int_at`

```python
def int_at(node: JsonMap, key: str, default: int = 0) -> int
```

``node[key]`` as an int (numeric text read, bools refused); ``default`` if absent or null.

### `object_at`

```python
def object_at(node: JsonMap, key: str) -> JsonObject
```

The object under ``node[key]``, empty when absent or null, an error for another type.

### `rows_at`

```python
def rows_at(node: JsonMap, key: str) -> list[JsonObject]
```

The list of objects under ``node[key]``, empty when absent or null.

### `ensure_object`

```python
def ensure_object(parent: JsonObject, key: str) -> JsonObject
```

The live object under ``parent[key]``, created empty when the key is absent or null.

