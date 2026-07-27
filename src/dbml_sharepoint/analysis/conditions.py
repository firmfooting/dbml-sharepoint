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

import re

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


# === Rendering ==============================================================
# Three targets, three syntaxes, none of them the author's problem. Every
# rule encoded below was established by running it against a live tenant
# and is recorded in the form_visibility spec; the differences are not
# stylistic and must not be harmonised.
#
#            reference        string literal          booleans
#   caml     <FieldRef/>      typed <Value>           <And>/<Or>
#   expr     [$X]             'x', '' doubles a quote &&  /  ||
#   valid    [X]              "x" (single REJECTED)   AND(...)/OR(...)

CAML = "caml"
EXPRESSION = "expression"
VALIDATION = "validation"

_CAML_OP_TAGS: dict[str, str] = {
    "eq": "Eq", "neq": "Neq", "lt": "Lt", "leq": "Leq", "gt": "Gt", "geq": "Geq",
    "is_null": "IsNull", "is_not_null": "IsNotNull",
    "contains": "Contains", "begins_with": "BeginsWith",
}
_EXPR_OPS: dict[str, str] = {
    "eq": "==", "neq": "!=", "lt": "<", "leq": "<=", "gt": ">", "geq": ">=",
}
_VALIDATION_OPS: dict[str, str] = {
    "eq": "=", "neq": "<>", "lt": "<", "leq": "<=", "gt": ">", "geq": ">=",
}

# Operators each target can render. A miss is a build error naming the
# target — never a formula emitted in hope.
CAPABILITIES: dict[str, frozenset[str]] = {
    CAML: frozenset(_CAML_OP_TAGS) | {"in", "not_in"},
    EXPRESSION: frozenset(_EXPR_OPS) | {"is_null", "is_not_null", "in", "not_in"},
    VALIDATION: frozenset(_VALIDATION_OPS) | {"is_null", "is_not_null", "in", "not_in"},
}

# Plausible from the documented syntax, never observed in a formula
# harvested from a live tenant. Being wrong about unexercised expression
# syntax has already happened twice in this work — once in the spec's own
# composition formulas — so unverified is treated as unknown, and the
# evidence probe is named in the error.
DISABLED_PENDING_PROBE: dict[str, frozenset[str]] = {
    EXPRESSION: frozenset({"contains", "not_contains", "begins_with", "not_begins_with"}),
}

_NUMBER_TYPES = frozenset({"int", "number", "calculated_number"})
_DATE_TYPES = frozenset({"date", "datetime", "calculated_date"})
_TODAY = re.compile(r"^today(?:([+-])(\d+))?$")


def _reject(target: str, reason: str, context: str) -> ValueError:
    return ValueError(f"{context}: {reason} (target: {target})")


def _check(leaf: Leaf, target: str, context: str) -> None:
    if leaf.op in DISABLED_PENDING_PROBE.get(target, frozenset()):
        raise _reject(
            target,
            f"operator {leaf.op!r} is not yet verified against a live tenant for this "
            f"target; confirm it with test/manual/form-visibility-evidence-probe.js "
            f"and enable it deliberately",
            context,
        )
    if leaf.op not in CAPABILITIES[target]:
        raise _reject(target, f"operator {leaf.op!r} has no rendering", context)
    if leaf.measure and target == CAML:
        raise _reject(target, "CAML has no LEN, so 'measure' cannot be rendered", context)
    if leaf.property and target == VALIDATION:
        raise _reject(
            target, "person and lookup operands are unsupported in validation formulas", context,
        )


def _is_today(value: object) -> bool:
    return isinstance(value, str) and bool(_TODAY.match(value))


def _xml_escape(text: str, extra: dict[str, str] | None = None) -> str:
    out = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    for char, entity in (extra or {}).items():
        out = out.replace(char, entity)
    return out


def _caml_value(column_type: str, value: object) -> str:
    if column_type == "boolean":
        return f'<Value Type="Integer">{"1" if value in (True, 1, "1") else "0"}</Value>'
    if column_type in _NUMBER_TYPES:
        return f'<Value Type="Number">{_xml_escape(str(value))}</Value>'
    if column_type in _DATE_TYPES:
        match = _TODAY.match(value) if isinstance(value, str) else None
        if match:
            sign, days = match.group(1), match.group(2)
            if days is None:
                return '<Value Type="DateTime"><Today/></Value>'
            offset = days if sign == "+" else f"-{days}"
            return f'<Value Type="DateTime"><Today OffsetDays="{offset}"/></Value>'
        return f'<Value Type="DateTime">{_xml_escape(str(value))}</Value>'
    return f'<Value Type="Text">{_xml_escape(str(value), {chr(34): "&quot;"})}</Value>'


def to_caml(condition: Condition, column_types: dict[str, str]) -> str:
    """Render to a CAML `<Where>` body."""
    return _render(normalise(condition), column_types, CAML, "conditions")


def to_expression(condition: Condition, column_types: dict[str, str]) -> str:
    """Render to a list-formatting predicate for `ClientValidationFormula`."""
    return _render(normalise(condition), column_types, EXPRESSION, "conditions")


def to_validation(condition: Condition, column_types: dict[str, str]) -> str:
    """Render to a classic validation predicate for `ValidationFormula`."""
    return _render(normalise(condition), column_types, VALIDATION, "conditions")


def _render(node: Condition, types: dict[str, str], target: str, context: str) -> str:
    if isinstance(node, Leaf):
        return _leaf(node, types, target, context)
    parts = [_render(child, types, target, context) for child in node.children]
    return _combine(parts, node.kind == "all_of", target)


def _combine(parts: list[str], conjunction: bool, target: str) -> str:
    if len(parts) == 1:
        return parts[0]
    if target == CAML:
        # CAML's And/Or are strictly binary; fold left, as the hand-rolled
        # view query did before this module existed.
        tag = "And" if conjunction else "Or"
        combined = parts[0]
        for nxt in parts[1:]:
            combined = f"<{tag}>{combined}{nxt}</{tag}>"
        return combined
    if target == EXPRESSION:
        # Parenthesised so precedence can never alter the declared meaning.
        return "(" + f" {'&&' if conjunction else '||'} ".join(parts) + ")"
    return f"{'AND' if conjunction else 'OR'}({','.join(parts)})"


def _leaf(leaf: Leaf, types: dict[str, str], target: str, context: str) -> str:
    _check(leaf, target, f"{context}.{leaf.field}")
    # A measure changes what is being compared: LEN(x) is a number
    # whatever x is, so the operand must not be quoted as the column
    # type would be.
    column_type = "number" if leaf.measure == "length" else types.get(leaf.field, "nvarchar")
    if _is_today(leaf.value) and target == EXPRESSION:
        raise _reject(
            target,
            "the 'today' sentinel has no verified client-side equivalent "
            "(@now carries datetime rather than date semantics)",
            f"{context}.{leaf.field}",
        )
    if leaf.op in ("in", "not_in"):
        values = leaf.value if isinstance(leaf.value, list) else [leaf.value]
        op = "eq" if leaf.op == "in" else "neq"
        parts = [
            _leaf(Leaf(leaf.field, op, v, leaf.property, leaf.measure), types, target, context)
            for v in values
        ]
        return _combine(parts, leaf.op == "not_in", target)
    if target == CAML:
        ref = f'<FieldRef Name="{leaf.field}"/>'
        tag = _CAML_OP_TAGS[leaf.op]
        if leaf.op in ("is_null", "is_not_null"):
            return f"<{tag}>{ref}</{tag}>"
        return f"<{tag}>{ref}{_caml_value(column_type, leaf.value)}</{tag}>"
    if target == EXPRESSION:
        ref = f"[${leaf.field}{'.' + leaf.property if leaf.property else ''}]"
        if leaf.measure == "length":
            ref = f"length({ref})"
        if leaf.op == "is_null":
            return f"{ref} == ''"
        if leaf.op == "is_not_null":
            return f"{ref} != ''"
        return f"{ref} {_EXPR_OPS[leaf.op]} {_expr_literal(column_type, leaf.value)}"
    ref = f"[{leaf.field}]"
    if leaf.measure == "length":
        ref = f"LEN({ref})"
    if leaf.op == "is_null":
        return f"ISBLANK({ref})"
    if leaf.op == "is_not_null":
        return f"NOT(ISBLANK({ref}))"
    return f"{ref}{_VALIDATION_OPS[leaf.op]}{_validation_literal(column_type, leaf.value)}"


def _expr_literal(column_type: str, value: object) -> str:
    if column_type == "boolean":
        return "true" if value in (True, 1, "1") else "false"
    if column_type in _NUMBER_TYPES and isinstance(value, (int, float)):
        return str(value)
    # Verified live: apostrophes escape by DOUBLING, not by backslash.
    return "'" + str(value).replace("'", "''") + "'"


def _validation_literal(column_type: str, value: object) -> str:
    today = _TODAY.match(str(value)) if isinstance(value, str) else None
    if today:
        sign, days = today.group(1), today.group(2)
        return "TODAY()" if days is None else f"TODAY(){sign}{days}"
    if column_type == "boolean":
        return "TRUE" if value in (True, 1, "1") else "FALSE"
    if column_type in _NUMBER_TYPES and isinstance(value, (int, float)):
        return str(value)
    # Verified live: validation literals are DOUBLE-quoted; single quotes
    # are rejected outright by SharePoint, the reverse of the expression
    # target three lines up.
    return '"' + str(value).replace('"', '""') + '"'
