# src/dbml_sharepoint/model/conditions.py
"""The shared condition grammar's types and structural parser.

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
"""

from dataclasses import dataclass
from typing import Any, Literal

from dbml_sharepoint.model._keys import _text_key
from dbml_sharepoint.model.errors import MappingShapeError, UnknownMappingKeyError

type GroupKind = Literal["all_of", "any_of", "none_of"]
GROUP_KINDS: tuple[GroupKind, ...] = ("all_of", "any_of", "none_of")

#: Operators that carry no `value`, which is a fact about the GRAMMAR rather
#: than about any target: `is_null` asks whether the column is empty, and there
#: is nothing to compare it against in any syntax.
#:
#: It lives here because both sides of the condition split need it and neither
#: may own it. `analysis.conditions` reads it to refuse a missing or surplus
#: value, and `analysis.condition_description` reads it to print the operator
#: with no operand after it -- and that module exists to be importable without
#: the validation stack, so it cannot reach across for a frozenset.
#: `test_condition_description.py` holds this module as the only owner.
VALUELESS_OPS: frozenset[str] = frozenset({"is_null", "is_not_null"})

_LEAF_KEYS = frozenset({"field", "op", "value", "property", "measure"})


@dataclass(frozen=True)
class Leaf:
    """One comparison.

    `property` reaches into a person or lookup column (rendering
    `[$Owner.title]`); `measure` compares a derived scalar such as length
    rather than the value itself. Both keep `op` and `value` uniform, which
    is why negation stays a simple operator flip and the De Morgan
    normaliser needs no special cases for either.
    """

    field: str
    op: str
    value: Any = None
    property: str | None = None
    measure: str | None = None


@dataclass(frozen=True)
class Group:
    """A boolean combination of conditions.

    `none_of` is accepted from authors but never survives normalisation.
    See `analysis.condition_rendering.normalise`.
    """

    kind: GroupKind
    children: tuple["Condition", ...]


type Condition = Leaf | Group


def parse_condition(raw: Any, context: str) -> Condition:
    """Parse a declared condition tree.

    A bare list is `all_of`: that is the spelling every existing
    `views[].where` already uses, so the grammar extends the flat list
    rather than replacing it.
    """
    if isinstance(raw, list):
        return _group("all_of", raw, context)
    if not isinstance(raw, dict):
        raise MappingShapeError(
            f"{context}: expected a mapping or a list of conditions, got {type(raw).__name__}",
        )
    raw_map: dict[object, object] = raw
    for key in raw_map:
        _text_key(key, context)

    present = [kind for kind in GROUP_KINDS if kind in raw_map]
    is_leaf = bool(_LEAF_KEYS & set(raw_map)) and not present
    if not is_leaf:
        if len(present) != 1:
            raise MappingShapeError(
                f"{context}: expected exactly one of {', '.join(GROUP_KINDS)}, "
                f"or a condition with 'field' and 'op'",
            )
        unknown = set(raw_map) - {present[0]}
        if unknown:
            raise UnknownMappingKeyError(
                f"{context}: unknown group key(s) {sorted(unknown, key=str)}",
            )
        return _group(present[0], raw_map[present[0]], context)

    unknown_leaf = set(raw_map) - _LEAF_KEYS
    if unknown_leaf:
        raise UnknownMappingKeyError(
            f"{context}: unknown key(s) {sorted(unknown_leaf, key=str)} on a condition",
        )
    required: dict[str, str] = {}
    for key in ("field", "op"):
        value = raw_map.get(key)
        # The type first, so `op: no` is not called missing; `require_str` is an import cycle.
        if value is not None and not isinstance(value, str):
            raise MappingShapeError(f"{context}.{key} must be a string, got {value!r}")
        if not value:
            raise MappingShapeError(f"{context}: {key!r} is required on a condition")
        required[key] = value
    optional: dict[str, str | None] = {}
    for key in ("property", "measure"):
        value = raw_map.get(key)
        if value is not None and not isinstance(value, str):
            raise MappingShapeError(f"{context}: {key!r} must be a string or null")
        optional[key] = value
    return Leaf(
        field=required["field"],
        op=required["op"],
        value=raw_map.get("value"),
        property=optional["property"],
        measure=optional["measure"],
    )


def _group(kind: GroupKind, items: Any, context: str) -> Group:
    if not isinstance(items, list):
        raise MappingShapeError(f"{context}.{kind}: expected a list of conditions")
    item_list: list[object] = items
    if not item_list:
        raise MappingShapeError(
            f"{context}.{kind}: empty group -- remove it or give it a condition",
        )
    children = tuple(
        parse_condition(item, f"{context}.{kind}[{index}]")
        for index, item in enumerate(item_list)
    )
    return Group(kind, children)
