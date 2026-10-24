---
title: naming
sidebar_position: 60
---

# `dbml_sharepoint.naming`

*slugs, kebab case and file stems, one rule each*

Fold names to slugs, kebab case and file stems, one rule each.

### `slug`

```python
def slug(text: str, *, sep: str = '-') -> str
```

``text`` lower-cased, each run outside ``[a-z0-9]`` turned into ``sep``.

``sep`` is ``-`` or ``_``. Raises ValueError when nothing is left, so a
caller cannot name a file or a key with an empty string.

### `kebab`

```python
def kebab(text: str) -> str
```

``text`` split at camel case, then slugged: ``MutedText`` gives ``muted-text``.

The split needs a lower-case letter or digit before the capital, so
``HTTPStatus`` gives ``httpstatus``.

### `file_stem`

```python
def file_stem(text: str) -> str
```

``text`` folded to what a file name and a directory name share.

Case is kept, each run outside ``[A-Za-z0-9._-]`` becomes ``-``, and
``-`` and ``.`` are stripped from both ends. Returns "" when nothing
usable is left, which the caller answers for itself.

