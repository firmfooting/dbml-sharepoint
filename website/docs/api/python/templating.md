---
title: templating
sidebar_position: 50
---

# `dbml_sharepoint.templating`

*Packaging: the shared Jinja environment*

The one canonical Jinja environment for every rendered artifact.

One constructor for every generator, including the ``comment_safe``
filter the pasteable scripts need. That means a rendering rule
(StrictUndefined so a missing variable fails the build instead of emitting
``undefined`` into a script, and the A5 header-injection guard) is fixed
in exactly one place.

### `TEMPLATES_DIR`

```python
TEMPLATES_DIR = Path("dbml_sharepoint/templates")
```

### `ApplicationNameError`

An application name the generated scripts cannot carry safely.

### `check_application_name`

```python
def check_application_name(application: str) -> None
```

Refuse a name that could escape a string, comment or attribute it is rendered into.

### `comment_safe`

```python
def comment_safe(value: object) -> str
```

Neutralise a block-comment terminator in raw header fields.

Provenance fields (site URL, source file names) are interpolated into
each script's leading ``/** ... */`` block; a crafted ``*/`` must not
close the comment and inject JS.

### `markdown_cell`

```python
def markdown_cell(value: object) -> str
```

Keep arbitrary text inside one Markdown table cell.

### `code_span`

```python
def code_span(value: object) -> str
```

A Markdown code span whose fence is longer than any backtick run inside the value.

### `ScriptEnvironment`

Jinja types `globals` by its defaults, which rejects data, so ours sit beside them.

#### `ScriptEnvironment.make_globals`

```python
def make_globals(self, d: MutableMapping[str, object] | None) -> ChainMap[str, object]
```

Make the globals map for a template. Any given template
globals overlay the environment :attr:`globals`.

Returns a :class:`collections.ChainMap`. This allows any changes
to a template's globals to only affect that template, while
changes to the environment's globals are still reflected.
However, avoid modifying any globals after a template is loaded.

:param d: Dict of template-specific globals.

.. versionchanged:: 3.0
    Use :class:`collections.ChainMap` to always prevent mutating
    environment globals.

### `script_env`

```python
def script_env(application: str = 'dbml-sharepoint') -> ScriptEnvironment
```

Environment for every generated artifact (scripts and manifests).

`application` is the identity the artifacts stamp; the version is the distribution's.

