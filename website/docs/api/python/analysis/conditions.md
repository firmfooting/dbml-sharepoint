---
title: conditions
sidebar_position: 20
---

# `dbml_sharepoint.analysis.conditions`

*classified condition diagnosis*

Semantic diagnosis for the shared condition grammar.

Rendering and target capability truth live in
:mod:`dbml_sharepoint.analysis.condition_rendering`. This module retains
classified Findings, source locations, operand diagnosis and deduplication.

BREAKING API MOVE (#168): import `CAML`, `EXPRESSION`, `VALIDATION`, `NEGATION`,
`CAPABILITIES`, `DISABLED_PENDING_PROBE`, `normalise`, `to_caml`,
`to_expression`, and `to_validation` from
`dbml_sharepoint.analysis.condition_rendering`. There are deliberately no
compatibility re-exports here.

### `MAX_DEPTH`

```python
MAX_DEPTH = 4
```

### `MAX_LEAVES`

```python
MAX_LEAVES = 32
```

### `measure_tree`

```python
def measure_tree(node: Condition) -> tuple[int, int]
```

`(group depth, leaf count)` for the bounds checks.

Counts POST-expansion: `in` with twenty values renders twenty
comparisons, so counting the authored leaf as one would let a tree
inside the cap render far past the formula length the cap exists to
protect.

### `condition_fields`

```python
def condition_fields(node: Condition) -> frozenset[str]
```

Every field referenced by a condition tree.

Values are deliberately ignored: valueless operators such as
``is_null`` still carry a field, while sentinels such as ``today`` are
operands rather than column references. The helper is shared by
checks that need the dependency set without rendering or re-walking
the grammar in their own way.

### `PROPERTY_ACCESSORS`

```python
PROPERTY_ACCESSORS = {'person': frozenset({'email', 'id', 'title'}), 'lookup': frozenset({'lookupId', 'lookupValue'})}
```

### `leaves`

```python
def leaves(node: Condition) -> list[dbml_sharepoint.model.conditions.Leaf]
```

Every leaf of a tree, in declaration order.

### `condition_findings`

```python
def condition_findings(condition: Condition, *, target: str, rendered: set[str], types: dict[str, str], lookups: set[str], at: dbml_sharepoint.analysis.findings.Location) -> list[dbml_sharepoint.analysis.findings.Finding]
```

Semantic problems with a declared condition, as classified Findings.

Every one is an error: a condition that cannot be rendered has no
degraded form to fall back to, so there is nothing to warn about.

A leaf's finding is located one element below `at`, which is exactly
what the message prefix has always spelled by hand.

