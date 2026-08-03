# src/dbml_sharepoint/model/conditions.py
"""The shared condition grammar's types and structural parser.

One grammar serves every conditional surface in the mapping —
`views[].where`, `form_visibility.when`, `column_validation.when` and
`list_validation.when` — because every SharePoint syntax difference the
alternative exposes is a rendering concern the author should never meet.
Those differences are not hypothetical: validation formulas reject single
quotes and require double, conditional-visibility expressions require
single and double an embedded apostrophe, one target spells booleans
`AND(...)` and the other `&&`, and column references are `[Col]` here and
`[$Col]` there. Authors who write target syntax by hand get those wrong
silently, because a malformed formula still saves and simply evaluates to
the wrong answer.

Structural checks only: shape, required keys, group arity. Anything needing
the schema — does this column exist, can this target render this operator —
lives in `analysis.conditions`, matching the parser/validator split used
everywhere else in this package.
"""

from dataclasses import dataclass
from typing import Any, Literal

GROUP_KINDS: tuple[str, ...] = ("all_of", "any_of", "none_of")

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

    `none_of` is accepted from authors but never survives normalisation —
    see `analysis.conditions.normalise`.
    """

    kind: Literal["all_of", "any_of", "none_of"]
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
        raise ValueError(
            f"{context}: expected a mapping or a list of conditions, got {type(raw).__name__}",
        )

    present = [kind for kind in GROUP_KINDS if kind in raw]
    is_leaf = bool(_LEAF_KEYS & set(raw)) and not present
    if not is_leaf:
        if len(present) != 1:
            raise ValueError(
                f"{context}: expected exactly one of {', '.join(GROUP_KINDS)}, "
                f"or a condition with 'field' and 'op'",
            )
        unknown = set(raw) - {present[0]}
        if unknown:
            raise ValueError(f"{context}: unknown group key(s) {sorted(unknown)}")
        return _group(present[0], raw[present[0]], context)

    unknown_leaf = set(raw) - _LEAF_KEYS
    if unknown_leaf:
        raise ValueError(f"{context}: unknown key(s) {sorted(unknown_leaf)} on a condition")
    for key in ("field", "op"):
        if not raw.get(key):
            raise ValueError(f"{context}: {key!r} is required on a condition")
    for key in ("property", "measure"):
        value = raw.get(key)
        if value is not None and not isinstance(value, str):
            raise ValueError(f"{context}: {key!r} must be a string or null")
    return Leaf(
        field=str(raw["field"]),
        op=str(raw["op"]),
        value=raw.get("value"),
        property=raw.get("property"),
        measure=raw.get("measure"),
    )


def _group(kind: str, items: Any, context: str) -> Group:
    if not isinstance(items, list):
        raise ValueError(f"{context}.{kind}: expected a list of conditions")
    if not items:
        raise ValueError(f"{context}.{kind}: empty group -- remove it or give it a condition")
    children = tuple(
        parse_condition(item, f"{context}.{kind}[{index}]") for index, item in enumerate(items)
    )
    return Group(kind, children)  # type: ignore[arg-type]
