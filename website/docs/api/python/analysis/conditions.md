---
title: conditions
sidebar_position: 11
---

# `dbml_sharepoint.analysis.conditions`

*condition normalisation, validation and rendering*

Normalisation, validation and rendering for the shared condition grammar.

`none_of` is eliminated here rather than at render time, because CAML has
no group-level negation: a renderer meeting a negated group would have
nothing to emit. De Morgan pushes negation down to the leaves, where every
operator has an exact inverse, so both renderers only ever see
`all_of`/`any_of` over positive leaves. That is the single property which
lets one authored grammar serve targets of very different expressive power.

The transformation is mechanical, terminating and depth-preserving:

    none_of[A, B]     ->  all_of[!A, !B]
    !(all_of[X, Y])   ->  any_of[!X, !Y]
    !(any_of[X, Y])   ->  all_of[!X, !Y]

Implications need no operator of their own. A validation rule is usually
"if A then B", which is `any_of[none_of[A], B]` — expressible in the
grammar as authored and normalised by the rules above.

### `NEGATION`

```python
NEGATION = {'eq': 'neq', 'neq': 'eq', 'lt': 'geq', 'geq': 'lt', 'gt': 'leq', 'leq': 'gt', 'is_null': 'is_not_null', 'is_not_null': 'is_null', 'in': 'not_in', 'not_in': 'in', 'contains': 'not_contains', 'not_cont…
```

### `MAX_DEPTH`

```python
MAX_DEPTH = 4
```

### `MAX_LEAVES`

```python
MAX_LEAVES = 32
```

### `normalise`

```python
def normalise(condition: Condition) -> Condition
```

Return an equivalent tree of `all_of`/`any_of` over positive leaves.

### `measure_tree`

```python
def measure_tree(node: Condition) -> tuple[int, int]
```

`(group depth, leaf count)` for the bounds checks.

Counts POST-expansion: `in` with twenty values renders twenty
comparisons, so counting the authored leaf as one would let a tree
inside the cap render far past the formula length the cap exists to
protect.

### `CAML`

```python
CAML = 'caml'
```

### `EXPRESSION`

```python
EXPRESSION = 'expression'
```

### `VALIDATION`

```python
VALIDATION = 'validation'
```

### `CAPABILITIES`

```python
CAPABILITIES = {'caml': frozenset({'begins_with', 'contains', 'eq', 'geq', 'gt', 'in', 'is_not_null', 'is_null', 'leq', 'lt', 'neq', 'not_in'}), 'expression': frozenset({'eq', 'geq', 'gt', 'in', 'is_not_null', 'is_n…
```

### `DISABLED_PENDING_PROBE`

```python
DISABLED_PENDING_PROBE = {'expression': frozenset({'begins_with', 'contains', 'not_begins_with', 'not_contains'})}
```

### `to_caml`

```python
def to_caml(condition: Condition, column_types: dict[str, str]) -> str
```

Render to a CAML `<Where>` body.

### `to_expression`

```python
def to_expression(condition: Condition, column_types: dict[str, str]) -> str
```

Render to a list-formatting predicate for `ClientValidationFormula`.

### `to_validation`

```python
def to_validation(condition: Condition, column_types: dict[str, str]) -> str
```

Render to a classic validation predicate for `ValidationFormula`.

### `SYSTEM_COLUMN_TYPES`

```python
SYSTEM_COLUMN_TYPES = {'ID': 'int', 'Created': 'datetime', 'Modified': 'datetime', 'Author': 'person', 'Editor': 'person'}
```

### `effective_column_types`

```python
def effective_column_types(declared: dict[str, str], cross_site_columns: set[str] | frozenset[str] = frozenset()) -> dict[str, str]
```

Types for DBML columns plus fields provisioned implicitly or by expansion.

### `PROPERTY_ACCESSORS`

```python
PROPERTY_ACCESSORS = {'person': frozenset({'email', 'id', 'title'}), 'lookup': frozenset({'lookupId', 'lookupValue'})}
```

### `leaves`

```python
def leaves(node: Condition) -> list[dbml_sharepoint.model.conditions.Leaf]
```

Every leaf of a tree, in declaration order.

### `validate_condition`

```python
def validate_condition(condition: Condition, *, target: str, rendered: set[str], types: dict[str, str], lookups: set[str], context: str) -> list[str]
```

Semantic problems with a declared condition, as messages.

Returns rather than raises, and keeps going after the first problem, so
one build reports every broken leaf instead of one per run. Messages are
wrapped into Findings by the caller — this module stays free of a
validator import, which would be a cycle.

### `describe`

```python
def describe(node: Condition) -> str
```

A human-readable summary for manifests and documentation.

Deliberately not any target's syntax: an operator reads as its declared
name, so an operator a reader does not recognise sends them to the
grammar reference rather than to a SharePoint dialect they would then
have to identify.

