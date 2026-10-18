---
title: yamlio
sidebar_position: 10
---

# `dbml_sharepoint.model.yamlio`

*read and write YAML by the package's own rules*

The YAML parser every file this package reads goes through, and the supported way for
downstream code to read and write YAML.

Public API: `safe_load`, `safe_dump`, `PARSE_ERRORS`, `TagOrDirectiveError` and
`RefusedYAMLError`. Downstream packages should call these and import neither
ruamel.yaml nor PyYAML, so their files are read by the rules below: YAML 1.2
safe load, a repeated key refused, an explicit tag or a `%YAML`/`%TAG`
directive refused. `safe_dump` writes block style, keys in their order, text as
written and no line wrapping, and its output reads back through `safe_load`
unchanged. Names with a leading underscore are internal.

It reads with ruamel.yaml 0.19.1's pure-Python safe loader, which reads
YAML 1.2: `yes`, `no`, `on` and `off` are text, `010` is 10 and `1:30` is
text. Until 2026-09 every file here was read by PyYAML, which reads YAML
1.1, where those are a boolean, 8 and 90. ruamel.yaml reads `1_000` and
`0b101` as numbers, as YAML 1.1 does, where the YAML 1.2 core schema
reads them as text.

The YAML spec requires the keys of a mapping to be unique. ruamel.yaml
checks, but not in a mapping that merges another nor inside the merged
one, so this loader refuses a repeated key itself (#672). It also refuses
an explicit tag and a `%YAML` or `%TAG` directive, which would read a
value by other rules, and the valid YAML `RefusedYAMLError` names (#686).

A leaf that imports only `ruamel.yaml`, so every module that parses YAML
can use it without importing another's parser. The mapping reader, the
release reader and the catalogue import none of one another; the wizard
imports the catalogue and the mapping loader, and parses one line of its
own through this module. `_keys.py` is shared across the parsers the same
way, though it imports `model.errors` and so is not a leaf.

### `PARSE_ERRORS`

```python
PARSE_ERRORS = (<class 'ruamel.yaml.error.YAMLError'>,)
```

### `TagOrDirectiveError`

A document that writes an explicit tag or a directive the loader refuses.

Every one found is listed with its line, up to `_MAX_LISTED`, so one run
names them all. `str()` begins "uses tags or directives", so a caller
can prefix the file's path.

### `RefusedYAMLError`

Valid YAML the loader refuses as it composes the document.

A reused anchor, a sequence or mapping used as a key, an alias inside
the collection its anchor names, and nesting deeper than `_MAX_DEPTH`,
counted through aliases. The YAML spec allows each; the loader refuses
them because ruamel.yaml would build a value no reader here expects or
can finish walking. `str()` is the marked message, so a caller can
prefix the file's path.

### `UniqueKeyConstructor`

ruamel.yaml's safe constructor, refusing a repeated key and any construction error.

A key written beside a merge (`<<: *anchor`) is not a repeat. It overrides
the merged key, as the merge-key spec documents, and a mapping may widen
one column of a merged view that way (the suite's reporting-sample
blueprint under test/fixtures/blueprints does).
A second `<<` in one mapping is a repeat. ruamel.yaml refuses it too,
but in words that name a setting this loader does not offer, so it is
refused here as any other repeat is.

The repeat check runs in `flatten_mapping`, the first place a mapping's
pairs are rewritten. A mapping used as a merge source is flattened into
its user before it is constructed itself, so a check in
`construct_mapping` would miss a repeat inside the source and read the
merged pairs of a nested merge as repeats. It runs before ruamel.yaml's
own check, which skips a mapping that merges.

#### `UniqueKeyConstructor.construct_object`

```python
def construct_object(self, node: Node, deep: bool = False) -> object
```

deep is True when creating an object/mapping recursively,
in that case want the underlying elements available during construction

#### `UniqueKeyConstructor.construct_yaml_timestamp`

```python
def construct_yaml_timestamp(self, node: object, values: object = None) -> object
```

#### `UniqueKeyConstructor.flatten_mapping`

```python
def flatten_mapping(self, node: MappingNode) -> None
```

This implements the merge key feature http://yaml.org/type/merge.html
by inserting keys from the merge dict/list of dicts if not yet
available in this node

#### `UniqueKeyConstructor.get_single_data`

```python
def get_single_data(self) -> object
```

### `safe_load`

```python
def safe_load(stream: str | IO[str]) -> object
```

ruamel.yaml's safe load, with the refusals the module docstring lists.

### `safe_dump`

```python
def safe_dump(data: object) -> str
```

`data` as YAML for an operator to edit and diff.

ruamel.yaml's safe writer quotes a string its reader would read as
another type, so the output reads back through `safe_load` unchanged.
A string holding NEL is double-quoted, which writes it as `\N`. Keys
keep their order, text is written as it is, and `width` is effectively
off: the default wraps a long scalar across lines, which is legal YAML
and unreadable in a diff, since a one-word edit to a validation message
reflows the whole block.

