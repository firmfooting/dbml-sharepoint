---
title: reading
sidebar_position: 5
---

# `dbml_sharepoint.model.reading`

*typed reads shared by the section families*

Typed reads shared by every section family.

One scalar off a YAML block, refusing the shapes YAML also accepts for it,
or one file the mapping names beside itself. Each helper carries the typo it
exists to refuse: `bool("false")` is True and a bare string iterates
character by character, and a value read leniently deploys the wrong thing
while the build reports success.

### `load_yaml`

```python
def load_yaml(path: pathlib.Path) -> dict[str, typing.Any]
```

Load a YAML file; require a top-level mapping (dict).

### `load_json_value`

```python
def load_json_value(base_dir: pathlib.Path, value: Any, context: str) -> dict[str, typing.Any]
```

A formatter declaration: a relative path to a JSON file (resolved
against the mapping's directory, like enum_sources) or an inline
mapping. Anything else (or malformed JSON) is a load error naming the
offending declaration.

### `strict_bool`

```python
def strict_bool(raw: collections.abc.Mapping[str, typing.Any], key: str, context: str, *, default: bool = True) -> bool
```

Read a boolean without truthiness-coercing malformed YAML.

`bool("false")` is True, so a quoted boolean would silently mean its
opposite, and a visibility flag reading backwards hides nothing while
reporting success.

`default` is the absent-key value, and it is a parameter only so a caller
whose default already has a home elsewhere can point at it rather than
restate it (see the `versioning.default` block, which reads its three
fallbacks off `Versioning`). The three form-visibility and permission
callers keep the true default they have always had.

### `optional_bool`

```python
def optional_bool(raw: collections.abc.Mapping[str, typing.Any], key: str, context: str, *, default: bool = False) -> bool
```

Read an optional boolean without truthiness-coercing malformed YAML.

`default` exists for the same reason `strict_bool`'s does: so a caller
whose fallback is declared elsewhere can name it instead of copying it.

### `optional_str`

```python
def optional_str(raw: collections.abc.Mapping[str, typing.Any], key: str, context: str) -> str | None
```

Read an optional string, refusing anything YAML happened to parse instead.

`display_column: [Title]` is a plausible typo and YAML accepts it as a list.
Passed through, it reaches a set-membership test deep in validation and
raises `TypeError: unhashable type: 'list'`, a traceback instead of the
ordinary "this column does not exist" error the author needed. Refuse the
shape here, where the context string can name the key.

### `require_int`

```python
def require_int(raw: collections.abc.Mapping[str, typing.Any], key: str, context: str) -> int
```

Read a required integer, refusing the bool YAML hands back for `yes`.

`isinstance(True, int)` is True in Python, so a plain int check passes a
boolean straight through and `int(True)` is 1. Both fields read this way
are ones where 1 is a legal-looking value, so nothing downstream can tell
the difference.

Subscripted, not `.get()`: an absent required key stays the KeyError it
has always been. Reporting that with a location is the error-model work
in #170, and doing it here would change an unrelated message.

### `optional_int`

```python
def optional_int(raw: collections.abc.Mapping[str, typing.Any], key: str, context: str) -> int | None
```

Read an optional integer, refusing bools and un-coercible strings.

`int(raw)` accepted three wrong things silently or badly: `yes` became 1,
`"100"` became 100 (so a quoted number worked by accident and taught the
wrong lesson), and `many` raised `invalid literal for int() with base 10`,
a message naming neither the key, the view, nor the entity.

### `require_str`

```python
def require_str(raw: collections.abc.Mapping[str, typing.Any], key: str, context: str) -> str
```

Read a required string. The mirror of `optional_str`.

Subscripted for the same reason as `require_int`.

### `optional_str_list`

```python
def optional_str_list(raw: collections.abc.Mapping[str, typing.Any], key: str, context: str) -> tuple[str, ...]
```

Read an optional list of strings, refusing the shapes YAML also accepts.

`hide_from_all_items: Author` is the plausible typo, and YAML hands it back
as a `str`, which iterates CHARACTER BY CHARACTER, so the column names
silently become 'A', 'u', 't', 'h'... and every one reports as a column that
does not exist. Refuse the shape here, where the context string can name the
key. `optional_str` is the mirror of this and deliberately rejects a list.

