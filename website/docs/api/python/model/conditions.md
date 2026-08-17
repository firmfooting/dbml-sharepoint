---
title: conditions
sidebar_position: 6
---

# `dbml_sharepoint.model.conditions`

*the shared condition grammar's types and parser*

The shared condition grammar's types and structural parser.

One grammar serves every conditional surface in the mapping
(`views[].where`, `form_visibility.when`, `column_validation.when` and
`list_validation.when`), because every SharePoint syntax difference the
alternative exposes is a rendering concern the author should never meet.
Those differences are not hypothetical: validation formulas reject single
quotes and require double, conditional-visibility expressions require
single and double an embedded apostrophe, one target spells booleans
`AND(...)` and the other `&&`, and column references are `[Col]` here and
`[$Col]` there. Authors who write target syntax by hand get those wrong
silently, because a malformed formula still saves and simply evaluates to
the wrong answer.

Structural checks only: shape, required keys, group arity. Anything needing
the schema (does this column exist, can this target render this operator)
lives in `analysis.conditions`, matching the parser/validator split used
everywhere else in this package.

### `GROUP_KINDS`

```python
GROUP_KINDS = ('all_of', 'any_of', 'none_of')
```

### `Leaf`

```python
@dataclass(frozen=True)
class Leaf:
    field: str
    op: str
    value: Any = None
    property: str | None = None
    measure: str | None = None
```

One comparison.

`property` reaches into a person or lookup column (rendering
`[$Owner.title]`); `measure` compares a derived scalar such as length
rather than the value itself. Both keep `op` and `value` uniform, which
is why negation stays a simple operator flip and the De Morgan
normaliser needs no special cases for either.

### `Group`

```python
@dataclass(frozen=True)
class Group:
    kind: typing.Literal['all_of', 'any_of', 'none_of']
    children: tuple['Condition', ...]
```

A boolean combination of conditions.

`none_of` is accepted from authors but never survives normalisation.
See `analysis.conditions.normalise`.

### `parse_condition`

```python
def parse_condition(raw: Any, context: str) -> Condition
```

Parse a declared condition tree.

A bare list is `all_of`: that is the spelling every existing
`views[].where` already uses, so the grammar extends the flat list
rather than replacing it.

