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

# Their own inverses, and never null-ambiguous.
_NULL_TESTS = frozenset({"is_null", "is_not_null"})

_FLIP: dict[str, str] = {"all_of": "any_of", "any_of": "all_of"}


def normalise(condition: Condition) -> Condition:
    """Return an equivalent tree of `all_of`/`any_of` over positive leaves."""
    return _push(condition, negate=False)


def _push(node: Condition, *, negate: bool) -> Condition:
    if isinstance(node, Leaf):
        if not negate:
            return node
        if node.op not in NEGATION:
            # Reached before the renderer's capability check, so an unknown
            # operator under none_of would otherwise surface as a bare
            # KeyError rather than a build error naming it.
            raise ValueError(
                f"cannot negate unknown operator {node.op!r} on {node.field!r}; "
                f"known operators: {', '.join(sorted(NEGATION))}",
            )
        flipped = Leaf(node.field, NEGATION[node.op], node.value, node.property, node.measure)
        if node.op in _NULL_TESTS or node.measure:
            # A null test is its own inverse, and a measure is never null —
            # LEN(blank) is 0, so the flipped comparison already matches.
            return flipped
        # SharePoint comparisons are three-valued: CAML's Neq and Leq do NOT
        # match rows where the column is empty, so a bare operator flip would
        # make "none of the items where Count > 5" exclude items with no
        # Count at all — which is the opposite of what the words say, and
        # disagrees with the expression target, where a blank coerces and is
        # included. Negation therefore admits the empty case explicitly, so
        # all three targets answer alike.
        return Group("any_of", (Leaf(node.field, "is_null", None, node.property), flipped))

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
    """`(group depth, leaf count)` for the bounds checks.

    Counts POST-expansion: `in` with twenty values renders twenty
    comparisons, so counting the authored leaf as one would let a tree
    inside the cap render far past the formula length the cap exists to
    protect."""
    if isinstance(node, Leaf):
        if node.op in ("in", "not_in") and isinstance(node.value, list):
            return (0, max(len(node.value), 1))
        return (0, 1)
    measured = [measure_tree(child) for child in node.children]
    return (1 + max(depth for depth, _ in measured), sum(count for _, count in measured))


# === Rendering ==============================================================
# Three targets, three syntaxes, none of them the author's problem. Every
# rule below was established by running it against a live tenant and is
# recorded in the form_visibility spec; the differences are not stylistic
# and must not be harmonised.
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

_TEXT_OPS = frozenset({"contains", "not_contains", "begins_with", "not_begins_with"})

# Operators each target can render. A miss is a build error naming the
# target — never a formula emitted in hope.
CAPABILITIES: dict[str, frozenset[str]] = {
    # CAML has Contains/BeginsWith but no negation of either.
    CAML: frozenset(_CAML_OP_TAGS) | {"in", "not_in"},
    EXPRESSION: frozenset(_EXPR_OPS) | {"is_null", "is_not_null", "in", "not_in"},
    VALIDATION: frozenset(_VALIDATION_OPS) | {"is_null", "is_not_null", "in", "not_in"} | _TEXT_OPS,
}

# Plausible from the documented syntax, never observed in a formula
# harvested from a live tenant. Being wrong about unexercised expression
# syntax has already happened twice in this work, so unverified is treated
# as unknown and the evidence probe is named in the error.
DISABLED_PENDING_PROBE: dict[str, frozenset[str]] = {
    EXPRESSION: _TEXT_OPS,
}

# Transforms a target cannot express at all, as opposed to merely unproven.
#
# `measure: length` on the expression target is the important one, and it is
# not an omission: list formatting's `length` returns an ARRAY's item count,
# and 1 or 0 for anything else — it does not measure a string. Rendering
# `length([$Note]) > 3` would therefore be false for every possible value,
# hiding the column unconditionally, with a formula that saves cleanly. The
# documented idiom is a sentinel trick (`indexOf([$Note] + '^', '^')`), which
# is not enabled here because it has not been run against a tenant.
_UNSUPPORTED_MEASURE: dict[str, str] = {
    CAML: "CAML has no LEN",
    EXPRESSION: (
        "list formatting's length() counts array items and returns 1/0 for other "
        "types — it does not measure a string, so the formula would be false for "
        "every value"
    ),
}
# CAML reaches a lookup's id via FieldRef LookupId, and a person's email not
# at all. Rendering the accessor away — comparing a display name to an email
# address — is a view that silently returns the wrong rows, so it is refused.
_UNSUPPORTED_PROPERTY: dict[str, str] = {
    CAML: "CAML cannot reach person or lookup sub-properties",
    VALIDATION: "person and lookup operands are unsupported in validation formulas",
}

_NUMBER_TYPES = frozenset({"int", "number", "calculated_number"})
_DATE_TYPES = frozenset({"date", "datetime", "calculated_date"})
_TODAY = re.compile(r"^today(?:([+-])(\d+))?$")
# True == 1 and False == 0 in Python, so the bare ints cover the bools.
_TRUTHY = frozenset({1, "1", "true", "True", "TRUE", "yes", "Yes", "YES"})
_FALSY = frozenset({0, "0", "false", "False", "FALSE", "no", "No", "NO"})
_VALUELESS_OPS = frozenset({"is_null", "is_not_null"})


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
    if leaf.measure and target in _UNSUPPORTED_MEASURE:
        raise _reject(
            target, f"'measure' cannot be rendered: {_UNSUPPORTED_MEASURE[target]}", context,
        )
    if leaf.property and target in _UNSUPPORTED_PROPERTY:
        raise _reject(target, _UNSUPPORTED_PROPERTY[target], context)
    if leaf.op not in _VALUELESS_OPS and leaf.value is None:
        raise _reject(target, f"operator {leaf.op!r} needs a 'value'", context)
    if leaf.op in _VALUELESS_OPS and leaf.value is not None:
        raise _reject(target, f"operator {leaf.op!r} takes no 'value'", context)
    if leaf.op in ("in", "not_in") and not isinstance(leaf.value, list):
        raise _reject(target, f"operator {leaf.op!r} needs a list 'value'", context)
    if leaf.op in ("in", "not_in") and not leaf.value:
        raise _reject(
            target,
            f"operator {leaf.op!r} has an empty list, which is a constant — say what "
            f"you mean with a condition rather than an empty set",
            context,
        )


def _xml_escape(text: str, extra: dict[str, str] | None = None) -> str:
    out = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    for char, entity in (extra or {}).items():
        out = out.replace(char, entity)
    return out


def _is_today(value: object, column_type: str) -> bool:
    """A `today` sentinel only means a date on a DATE column. On a text
    column it is the literal word, and reading it as TODAY() would give one
    authored condition three different meanings across the three targets."""
    return column_type in _DATE_TYPES and isinstance(value, str) and bool(_TODAY.match(value))


def _number(value: object, context: str, target: str) -> str:
    """A numeric column's operand is emitted bare. The declared type is
    authoritative: a value that is not a number on a numeric column is a
    build error, not a silent string comparison where '10' < '5'."""
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise _reject(target, f"{value!r} is not a number", context)
    try:
        return str(int(value)) if float(value).is_integer() else str(float(value))
    except ValueError:
        raise _reject(target, f"{value!r} is not a number on a numeric column", context) from None


def _boolean(value: object, context: str, target: str) -> bool:
    """Coercion is two-sided. A one-sided test silently inverts the
    condition for the author who quotes 'true', which is the cautious
    thing to do and so exactly the author who should not be punished."""
    if value in _TRUTHY:
        return True
    if value in _FALSY:
        return False
    raise _reject(target, f"{value!r} is not a boolean", context)


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
    return _combine(parts, conjunction=node.kind == "all_of", target=target)


def _combine(parts: list[str], *, conjunction: bool, target: str) -> str:
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


def _column_type(field: str, types: dict[str, str], target: str, context: str) -> str:
    """The declared type drives literal rendering, so an unknown column is
    an error rather than a silent 'nvarchar'. A date column defaulting to
    text renders `<Value Type="Text">today-30</Value>`, which SharePoint
    accepts and answers with the wrong rows."""
    if field not in types:
        raise _reject(target, f"no declared type for column {field!r}", context)
    return types[field]


def _leaf(leaf: Leaf, types: dict[str, str], target: str, context: str) -> str:
    where = f"{context}.{leaf.field}"
    _check(leaf, target, where)
    # A measure changes what is compared: LEN(x) is a number whatever x is.
    column_type = (
        "number" if leaf.measure == "length" else _column_type(leaf.field, types, target, where)
    )

    if leaf.op in ("in", "not_in"):
        op = "eq" if leaf.op == "in" else "neq"
        parts = [
            _leaf(Leaf(leaf.field, op, item, leaf.property, leaf.measure), types, target, context)
            for item in leaf.value
        ]
        return _combine(parts, conjunction=leaf.op == "not_in", target=target)

    if _is_today(leaf.value, column_type) and target == EXPRESSION:
        raise _reject(
            target,
            "the 'today' sentinel has no verified client-side equivalent "
            "(@now carries datetime rather than date semantics)",
            where,
        )

    if target == CAML:
        ref = f'<FieldRef Name="{leaf.field}"/>'
        tag = _CAML_OP_TAGS[leaf.op]
        if leaf.op in _VALUELESS_OPS:
            return f"<{tag}>{ref}</{tag}>"
        return f"<{tag}>{ref}{_caml_value(column_type, leaf.value, where)}</{tag}>"

    if target == EXPRESSION:
        ref = f"[${leaf.field}{'.' + leaf.property if leaf.property else ''}]"
        if leaf.op == "is_null":
            return f"{ref} == ''"
        if leaf.op == "is_not_null":
            return f"{ref} != ''"
        return f"{ref} {_EXPR_OPS[leaf.op]} {_expr_literal(column_type, leaf.value, where)}"

    return _validation_leaf(leaf, column_type, where)


def _validation_leaf(leaf: Leaf, column_type: str, where: str) -> str:
    ref = f"LEN([{leaf.field}])" if leaf.measure == "length" else f"[{leaf.field}]"
    if leaf.op == "is_null":
        return f"ISBLANK({ref})"
    if leaf.op == "is_not_null":
        return f"NOT(ISBLANK({ref}))"
    literal = _validation_literal(column_type, leaf.value, where)
    if leaf.op in ("contains", "not_contains"):
        rendered = f"ISNUMBER(FIND({literal},{ref}))"
        return f"NOT({rendered})" if leaf.op == "not_contains" else rendered
    if leaf.op in ("begins_with", "not_begins_with"):
        rendered = f"LEFT({ref},{len(str(leaf.value))})={literal}"
        return f"NOT({rendered})" if leaf.op == "not_begins_with" else rendered
    return f"{ref}{_VALIDATION_OPS[leaf.op]}{literal}"


def _caml_value(column_type: str, value: object, where: str) -> str:
    if column_type == "boolean":
        return f'<Value Type="Integer">{"1" if _boolean(value, where, CAML) else "0"}</Value>'
    if column_type in _NUMBER_TYPES:
        return f'<Value Type="Number">{_number(value, where, CAML)}</Value>'
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


def _expr_literal(column_type: str, value: object, where: str) -> str:
    if column_type == "boolean":
        return "true" if _boolean(value, where, EXPRESSION) else "false"
    if column_type in _NUMBER_TYPES:
        return _number(value, where, EXPRESSION)
    # Verified live: apostrophes escape by DOUBLING, not by backslash.
    return "'" + str(value).replace("'", "''") + "'"


def _validation_literal(column_type: str, value: object, where: str) -> str:
    if _is_today(value, column_type):
        match = _TODAY.match(str(value))
        sign, days = (match.group(1), match.group(2)) if match else (None, None)
        return "TODAY()" if days is None else f"TODAY(){sign}{days}"
    if column_type == "boolean":
        return "TRUE" if _boolean(value, where, VALIDATION) else "FALSE"
    if column_type in _NUMBER_TYPES:
        return _number(value, where, VALIDATION)
    # Verified live: validation literals are DOUBLE-quoted; single quotes are
    # rejected outright by SharePoint, the reverse of the expression target.
    # The doubling escape for an embedded double quote is the Excel
    # convention but was NOT among the harvested formulas — see the spec's
    # open items.
    return '"' + str(value).replace('"', '""') + '"'


# === Semantic validation ====================================================
# Types for the columns SharePoint provides but DBML never declares. Views
# may reference these, and without them a date comparison on Created would
# render as Type="Text" — which SharePoint accepts and answers with the
# wrong rows.
SYSTEM_COLUMN_TYPES: dict[str, str] = {
    "ID": "int",
    "Created": "datetime",
    "Modified": "datetime",
    "Author": "person",
    "Editor": "person",
}

# There is no defensible default between a person's display name, their
# email and their id, so the accessor is declared rather than guessed.
PROPERTY_ACCESSORS: dict[str, frozenset[str]] = {
    "person": frozenset({"title", "email", "id"}),
    "lookup": frozenset({"lookupValue", "lookupId"}),
}
_MEASURABLE_TYPES = frozenset({"nvarchar", "longtext", "richtext", "calculated_text"})

_RENDERERS = {CAML: to_caml, EXPRESSION: to_expression, VALIDATION: to_validation}


def leaves(node: Condition) -> list[Leaf]:
    """Every leaf of a tree, in declaration order."""
    if isinstance(node, Leaf):
        return [node]
    return [leaf for child in node.children for leaf in leaves(child)]


def validate_condition(
    condition: Condition,
    *,
    target: str,
    rendered: set[str],
    types: dict[str, str],
    lookups: set[str],
    context: str,
) -> list[str]:
    """Semantic problems with a declared condition, as messages.

    Returns rather than raises, and keeps going after the first problem, so
    one build reports every broken leaf instead of one per run. Messages are
    wrapped into Findings by the caller — this module stays free of a
    validator import, which would be a cycle.
    """
    problems: list[str] = []
    depth, leaf_count = measure_tree(condition)
    if depth > MAX_DEPTH:
        problems.append(f"{context}: nested {depth} groups deep; the limit is {MAX_DEPTH}")
    if leaf_count > MAX_LEAVES:
        problems.append(
            f"{context}: {leaf_count} conditions after expanding any 'in' lists; "
            f"the limit is {MAX_LEAVES}",
        )

    for leaf in leaves(condition):
        where = f"{context}.{leaf.field}"
        if leaf.field not in rendered:
            problems.append(f"{where}: not a rendered column")
            continue
        if leaf.op not in NEGATION:
            problems.append(
                f"{where}: unknown operator {leaf.op!r}; "
                f"known operators: {', '.join(sorted(NEGATION))}",
            )
            continue
        problems.extend(_operand_problems(leaf, where, types=types, lookups=lookups))

    if problems:
        # Rendering a leaf whose operands are already wrong would report the
        # same fault twice in different words.
        return problems
    return _render_problems(condition, target, types, context)


def _operand_problems(
    leaf: Leaf, where: str, *, types: dict[str, str], lookups: set[str],
) -> list[str]:
    column_type = types.get(leaf.field, "")
    kind = "lookup" if leaf.field in lookups else column_type
    problems: list[str] = []
    if kind in PROPERTY_ACCESSORS:
        allowed = PROPERTY_ACCESSORS[kind]
        if not leaf.property:
            problems.append(
                f"{where}: a {kind} column needs 'property' "
                f"(one of {', '.join(sorted(allowed))})",
            )
        elif leaf.property not in allowed:
            problems.append(
                f"{where}: {leaf.property!r} is not a {kind} accessor; "
                f"use one of {', '.join(sorted(allowed))}",
            )
    elif leaf.property:
        problems.append(f"{where}: 'property' applies to person and lookup columns only")
    if leaf.measure and leaf.measure != "length":
        problems.append(f"{where}: unknown measure {leaf.measure!r}; only 'length' is supported")
    if leaf.measure and column_type not in _MEASURABLE_TYPES:
        problems.append(f"{where}: 'measure: length' applies to text columns only")
    return problems


def _render_problems(
    condition: Condition, target: str, types: dict[str, str], context: str,
) -> list[str]:
    """Reuse the renderer as the capability oracle, one leaf at a time, so a
    second copy of the capability rules cannot drift from the first."""
    problems: list[str] = []
    for leaf in leaves(normalise(condition)):
        try:
            _RENDERERS[target](leaf, types)
        except ValueError as exc:
            message = str(exc).replace("conditions.", f"{context}.", 1)
            if message not in problems:
                problems.append(message)
    return problems


def describe(node: Condition) -> str:
    """A human-readable summary for manifests and documentation.

    Deliberately not any target's syntax: an operator reads as its declared
    name, so an operator a reader does not recognise sends them to the
    grammar reference rather than to a SharePoint dialect they would then
    have to identify.
    """
    if isinstance(node, Leaf):
        subject = f"{node.field}.{node.property}" if node.property else node.field
        if node.measure:
            subject = f"{node.measure}({subject})"
        if node.op in _NULL_TESTS:
            return f"{subject} {node.op}"
        return f"{subject} {node.op} {node.value!r}"
    joiner = {"all_of": " AND ", "any_of": " OR ", "none_of": " NOR "}[node.kind]
    inner = joiner.join(describe(child) for child in node.children)
    return inner if len(node.children) == 1 else f"({inner})"
