---
title: condition_rendering
sidebar_position: 19
---

# `dbml_sharepoint.analysis.condition_rendering`

*condition normalisation and target rendering*

Normalisation and rendering for the shared condition grammar.

This module is dependency-light by design. It owns target capability truth and
raises renderer-neutral refusals; diagnosis translates those refusals into
classified diagnostics in :mod:`dbml_sharepoint.analysis.conditions`.

BREAKING API MOVE (#168): import rendering constants and functions from
`dbml_sharepoint.analysis.condition_rendering`. They are not re-exported from
`dbml_sharepoint.analysis.conditions`.

### `ConditionRefusalKind`

Renderer-neutral identities for failures to render a condition.

### `ConditionRefusal`

A rendering refusal with stable identity and source coordinates.

### `NEGATION`

```python
NEGATION = {'eq': 'neq', 'neq': 'eq', 'lt': 'geq', 'geq': 'lt', 'gt': 'leq', 'leq': 'gt', 'is_null': 'is_not_null', 'is_not_null': 'is_null', 'in': 'not_in', 'not_in': 'in', 'contains': 'not_contains', 'not_cont…
```

### `normalise`

```python
def normalise(condition: Condition) -> Condition
```

Return an equivalent tree of `all_of`/`any_of` over positive leaves.

### `normalise_with_polarity`

```python
def normalise_with_polarity(condition: Condition, *, negated: bool) -> Condition
```

Normalise one authored occurrence under its inherited negation state.

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

### `CAML_VIEW_FILTER_GUARD`

```python
CAML_VIEW_FILTER_GUARD = '<Or><IsNotNull><FieldRef Name="ID"/></IsNotNull><IsNull><FieldRef Name="ID"/></IsNull></Or>'
```

### `CAPABILITIES`

```python
CAPABILITIES = {'caml': frozenset({'begins_with', 'contains', 'eq', 'geq', 'gt', 'in', 'includes', 'is_not_null', 'is_null', 'leq', 'lt', 'neq', 'not_in', 'not_includes'}), 'expression': frozenset({'begins_with', 'c…
```

### `DISABLED_PENDING_PROBE`

```python
DISABLED_PENDING_PROBE = {}
```

### `is_current_user_sentinel`

```python
def is_current_user_sentinel(value: object, column_type: str) -> bool
```

A `me` sentinel only means the current user on a PERSON column. On a
text column it is the literal word, the same rule `today` follows, and
for the same reason: one authored condition must not mean three
different things across the three targets.

### `to_caml`

```python
def to_caml(condition: Condition, column_types: dict[str, str]) -> str
```

Render to a CAML `<Where>` body.

### `to_caml_protected`

```python
def to_caml_protected(condition: Condition, column_types: dict[str, str]) -> str
```

Render a VIEW's `<Where>` body in the shape the filter editor refuses.

A separate function rather than a `protected` flag on `to_caml`, because
`to_caml` is an entry in `_RENDERERS` and is dispatched there as
`(condition, types)` to decide what a target can express. A required flag
would break that registry, and a defaulted one would let a future view
path emit an unguarded filter with nothing to say so.

The editor refuses a filter whose right child is a group, and a view it
cannot open it cannot truncate (measured 2026-08-17 on
`caml-chain-depth-probe.js`, by
`view.filter-editor.wrapper-group-left-editable`,
`view.filter-editor.wrapper-group-right-editable` and
`view.filter-editor.tautology-guard-editable`).

### `caml_condition_count`

```python
def caml_condition_count(condition: Condition, column_types: dict[str, str]) -> int
```

How many comparisons the rendered CAML presents to the filter editor.

Not the tree's leaf count. `neq` and `not_includes` each render an
`<IsNull>` arm beside the comparison, and `not_in` renders one for the
whole group, so six authored `neq` clauses render twelve comparisons. The
editor shows a row per comparison, so that larger number is the one an
author is warned about.

Counted on the UNGUARDED form: the guard adds two comparisons of its own
and is not something the author wrote.

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

