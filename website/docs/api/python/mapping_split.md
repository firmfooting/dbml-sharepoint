---
title: mapping_split
sidebar_position: 53
---

# `dbml_sharepoint.mapping_split`

*Packaging: split a mapping.yaml into its concern files, as text*

Split a `mapping.yaml` into its concern files, as text.

Each top-level block moves verbatim, with the comments above it, so comments
and quoting survive and the operator reviews a move rather than a rewrite.
The pieces are parsed back and compared with the mapping before anything is
written. The concern files are written first and the mapping is replaced
last, in one rename: a failed write leaves a section in two homes, which the
loader refuses, never in none.

### `SplitRefusedError`

The converter's one refusal. Its text is the operator's message; nothing was written.

### `SplitPlan`

```python
@dataclass(frozen=True)
class SplitPlan:
    texts: dict[str, str]
    moved: dict[str, tuple[str, ...]]
```

What a split would write, and which keys it would move.

### `plan_split`

```python
def plan_split(mapping_path: Path) -> SplitPlan
```

What splitting `mapping_path` would write, verified. Writes nothing.

### `split_mapping`

```python
def split_mapping(mapping_path: Path) -> dict[str, tuple[str, ...]]
```

Split `mapping_path` into its concern files and return the keys moved into each.

