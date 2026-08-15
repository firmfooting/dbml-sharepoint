---
title: templating
sidebar_position: 23
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

### `comment_safe`

```python
def comment_safe(value: object) -> str
```

Neutralise a block-comment terminator in raw header fields.

Provenance fields (site URL, source file names) are interpolated into
each script's leading ``/** … */`` block; a crafted ``*/`` must not
close the comment and inject JS.

### `script_env`

```python
def script_env() -> jinja2.environment.Environment
```

Environment for every generated artifact (scripts and manifests).

