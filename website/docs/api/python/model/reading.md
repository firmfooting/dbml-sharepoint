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

A blank key follows one rule (decided on #665), and every reader here keeps it:

- An absent key takes its default, silently.
- A key written with no value (`direction:`, which YAML reads as null) reads
  as absent, so it takes its default too.
- Where that default decides how the deployed lists behave, the blank is
  recorded as a `BlankDefault` and validation warns with
  `blank_key_took_default`, because the author may have meant a value. That
  is any boolean, a vocabulary word (`direction`, `reconcile`, `trigger`,
  `owner_group`, item_security `read` and `write`, a view's `scope`), a
  condition (`where`, `when`), a `from_enum` source, `major_version_limit`,
  a view's `row_limit`, an entity's `title`, the default permission policy's
  `site_role`, and a policy's `assignments` (under `reconcile: exact` an
  empty grant list strips every grant).
- Where the default is empty text, an empty list or a value that changes
  nothing (`description`, `notes`, `extension`, a style guard's `not`), a
  blank stays silent, because it can only mean nothing.
- A required key left blank is refused as `{context}.{key} is required`.
- A value of the wrong type is refused.
- Where null is itself a documented value, it keeps that meaning and takes
  no default. A condition's `value: null` is carried as written and judged
  by its operator, and a `style_theme` token's `icon: null` shows no icon,
  where an absent `icon` takes the token's own.

Recording happens only inside `recording_blank_defaults()`, which
`load_mapping` opens around the section families. Outside it a blank still
takes its default, without a record.

### `recording_blank_defaults`

```python
def recording_blank_defaults() -> collections.abc.Iterator[list[dbml_sharepoint.model.mapping_types.BlankDefault]]
```

Collect the blank keys that took a behavioural default, for one load.

### `optional_value`

```python
def optional_value(raw: collections.abc.Mapping[str, typing.Any], key: str, context: str, *, default: object = None) -> Any
```

The untyped value under `key`, or `default` when it is absent or blank.

For a key whose default is itself a behaviour (no condition, no enum to
expand, a style's boolean) and whose value the caller types, so a blank
is recorded as taking `default`.

### `drop_blank_keys`

```python
def drop_blank_keys(block: collections.abc.Mapping[str, object], context: str, defaults: collections.abc.Mapping[str, object]) -> dict[str, object]
```

`block` without its blank keys, each recorded as taking `defaults[key]`.

For a block stored raw and merged later, where a blank left in place would
reach the merge as None rather than as absent. `defaults` must name every
key the caller admitted.

### `read_yaml_document`

```python
def read_yaml_document(path: pathlib.Path, named_by: str | None = None) -> Any
```

Parse one YAML file, naming every way reading it can fail.

`yaml.YAMLError` and the `OSError` from opening the file are neither of
them a `MappingError`, so a caller switching on the base class used to
miss the two most ordinary failures there are: a mapping with a typo
that stops it parsing, and a source file that is not where the mapping
says. The original is kept as `__cause__`, and the parser's own text is
passed through because it carries the line and column, which is the part
an author can act on.

Decoding is the third way, and it is the one that hides: the bytes turn
into text inside `yaml.safe_load`, so a file that is not UTF-8 raises
`UnicodeDecodeError` past both of the other handlers. It is a
`ValueError` subclass, so it reached a caller catching `ValueError`
looking exactly like a refusal this module composed.

`named_by` is the declaration that pointed at this file, when one did.
An unreadable file is then the reference that did not resolve, which is
what `MappingReferenceError` documents; a path the caller supplied has
no declaration to blame, so it is the document itself that failed.

### `load_yaml`

```python
def load_yaml(path: pathlib.Path, named_by: str | None = None) -> dict[str, typing.Any]
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

A blank key takes `default` and is recorded, as the module docstring says.

### `optional_bool`

```python
def optional_bool(raw: collections.abc.Mapping[str, typing.Any], key: str, context: str, *, default: bool = False) -> bool
```

Read an optional boolean without truthiness-coercing malformed YAML.

`default` exists for the same reason `strict_bool`'s does: so a caller
whose fallback is declared elsewhere can name it instead of copying it.
A blank key takes it and is recorded, as `strict_bool`'s does.

### `optional_str`

```python
def optional_str(raw: collections.abc.Mapping[str, typing.Any], key: str, context: str, *, record_blank: bool = False) -> str | None
```

Read an optional string, refusing anything YAML happened to parse instead.

`display_column: [Title]` is a plausible typo and YAML accepts it as a list.
Passed through, it reaches a set-membership test deep in validation and
raises `TypeError: unhashable type: 'list'`, a traceback instead of the
ordinary "this column does not exist" error the author needed. Refuse the
shape here, where the context string can name the key.

`record_blank` is for a key whose absence is itself a behaviour (an
entity's `title` falls back to the derived list title): a blank one is
recorded as taking None. Off by default, so `extension:` stays silent.

### `strict_str`

```python
def strict_str(raw: collections.abc.Mapping[str, typing.Any], key: str, context: str, *, default: str) -> str
```

Read a string that falls back to a default the author should hear about.

An absent key and a blank one (`direction:` with nothing after it) both
take the default, and the blank is recorded, as the module docstring
says. That record is the whole difference from `optional_str`.

Use it wherever the fallback is a CHOICE the loader would otherwise make
silently. Where the fallback is the empty value of the same kind (`""`
for free text, `()` for a list of names), a blank can only mean nothing
and `optional_str` is the reader.

### `require_int`

```python
def require_int(raw: collections.abc.Mapping[str, typing.Any], key: str, context: str) -> int
```

Read a required integer, refusing the bool YAML hands back for `yes`.

`isinstance(True, int)` is True in Python, so a plain int check passes a
boolean straight through and `int(True)` is 1. Both fields read this way
are ones where 1 is a legal-looking value, so nothing downstream can tell
the difference.

An absent key is a `MappingShapeError` naming the key path, not the bare
KeyError this subscripted before #170: the hierarchy claims an absent
required key, so a caller catching `MappingError` has to get one.

### `optional_int`

```python
def optional_int(raw: collections.abc.Mapping[str, typing.Any], key: str, context: str, *, record_blank: bool = False) -> int | None
```

Read an optional integer, refusing bools and un-coercible strings.

`int(raw)` accepted three wrong things silently or badly: `yes` became 1,
`"100"` became 100 (so a quoted number worked by accident and taught the
wrong lesson), and `many` raised `invalid literal for int() with base 10`,
a message naming neither the key, the view, nor the entity.

`record_blank` works as `optional_str`'s does (a view's `row_limit`).

### `require_str`

```python
def require_str(raw: collections.abc.Mapping[str, typing.Any], key: str, context: str) -> str
```

Read a required string. The mirror of `optional_str`.

Refuses an absent or blank key the same way `require_int` does.

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

