# src/dbml_sharepoint/analysis/conditions.py
"""Normalisation, validation and rendering for the shared condition grammar.

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
"""

from dbml_sharepoint.model.conditions import Condition, Group, Leaf

# Every operator's exact inverse. The involution is asserted by a test: an
# operator added here without one silently breaks `none_of`, because the
# normaliser would have nothing to flip it to.
NEGATION: dict[str, str] = {
    "eq": "neq",
    "neq": "eq",
    "lt": "geq",
    "geq": "lt",
    "gt": "leq",
    "leq": "gt",
    "is_null": "is_not_null",
    "is_not_null": "is_null",
    "in": "not_in",
    "not_in": "in",
    "contains": "not_contains",
    "not_contains": "contains",
    "begins_with": "not_begins_with",
    "not_begins_with": "begins_with",
}

# Bounds keep a pathological declaration a build error rather than a
# formula truncated at whatever limit the target happens to impose.
MAX_DEPTH = 4
MAX_LEAVES = 32

_FLIP: dict[str, str] = {"all_of": "any_of", "any_of": "all_of"}


def normalise(condition: Condition) -> Condition:
    """Return an equivalent tree of `all_of`/`any_of` over positive leaves."""
    return _push(condition, negate=False)


def _push(node: Condition, *, negate: bool) -> Condition:
    if isinstance(node, Leaf):
        if not negate:
            return node
        return Leaf(node.field, NEGATION[node.op], node.value, node.property, node.measure)

    if node.kind == "none_of":
        # none_of[C] == all_of[!C];  !none_of[C] == any_of[C].
        kind = "any_of" if negate else "all_of"
        child_negate = not negate
    else:
        kind = _FLIP[node.kind] if negate else node.kind
        child_negate = negate

    children = tuple(_push(child, negate=child_negate) for child in node.children)
    return Group(kind, children)  # type: ignore[arg-type]


def measure_tree(node: Condition) -> tuple[int, int]:
    """`(group depth, leaf count)` for the bounds checks."""
    if isinstance(node, Leaf):
        return (0, 1)
    measured = [measure_tree(child) for child in node.children]
    return (1 + max(depth for depth, _ in measured), sum(count for _, count in measured))
