# src/dbml_sharepoint/extract/inverse.py
"""Recovering mapping declarations from the artifacts they generated.

Every function here returns a candidate declaration or `None`, and a
candidate is only returned once the SHIPPED FORWARD GENERATOR has been re-run
over it and reproduced the observed artifact exactly. The extractor never
asserts that a formatter means a particular style spec; it proposes one and
checks, so a wrong guess degrades to "preserved raw and reported" rather
than to a mapping that builds cleanly and deploys something else.

That rule is what lets this module hold parsers loose enough to be readable.
The parsing can be approximate because the verification is exact.
"""

import json
import re
from typing import Any

from dbml_sharepoint.analysis.condition_rendering import to_expression, to_validation
from dbml_sharepoint.analysis.forms import compose_visibility
from dbml_sharepoint.analysis.styles import TOKENS, expand_style
from dbml_sharepoint.analysis.typemap import DATE_TYPES, NUMBER_TYPES
from dbml_sharepoint.model.conditions import Condition, parse_condition

#: The suffix `_severity` appends to its class expression.
_SEVERITY_TEXT_SUFFIX = " + ' ms-fontColor-neutralSecondary'"

#: One arm of a generated `=if(...)` chain, in either of the two condition
#: spellings `styles._condition` emits (plain, and the `calculated: true`
#: form that reads past SharePoint's `string;#` prefix).
_ARM = re.compile(
    r"if\((?:@currentField == '((?:[^']|'')*)'"
    r"|indexOf\(@currentField, '((?:[^']|'')*)'\) >= 0), "
    r"'([^']*)', ",
)

#: A `[$InternalName]` column reference in a list-formatting expression.
_EXPR_REF = re.compile(r"\[\$([A-Za-z_][A-Za-z0-9_]*)\]")

#: A `[Name]` or bare `Name` column reference in a validation formula.
#: SharePoint strips brackets it does not need, so both spellings occur.
_VALIDATION_REF = r"(?:\[(?P<braced>[^\]]+)\]|(?P<bare>[A-Za-z_][A-Za-z0-9_]*))"

#: Expression-target comparison operators, observed spelling to authored name.
_EXPR_OPS = {"==": "eq", "!=": "neq", "<=": "leq", ">=": "geq", "<": "lt", ">": "gt"}

#: Validation-target comparison operators. `<>` before `<` matters: a
#: left-to-right scan would otherwise split `<>` into `<` and a stray `>`.
_VALIDATION_OPS = [("<>", "neq"), ("<=", "leq"), (">=", "geq"),
                   ("=", "eq"), ("<", "lt"), (">", "gt")]

#: `compose_visibility`'s per-form gates, as it spells them.
_NEW_ONLY = "[$ID] == ''"
_EXISTING_ONLY = "[$ID] != ''"

#: Reverse of `styles.TOKENS`. Inverting is only well defined while no two
#: tokens share a class string, so `test_extract.py` pins that separately;
#: a collision here would silently pick whichever token was declared last.
_TOKEN_BY_CLASSES = {token.classes: name for name, token in TOKENS.items()}


def _unquote(text: str) -> str:
    """Undo the `''` doubling a generated single-quoted literal carries."""
    return text.replace("''", "'")


def _canonical(formatter: object) -> str:
    """One spelling for a formatter, so two can be compared for sameness."""
    return json.dumps(formatter, separators=(",", ":"), sort_keys=True)


# === Column formatting ======================================================


def _severity_candidate(formatter: dict[str, Any]) -> dict[str, Any] | None:
    """A `severity` or `pill` spec proposed from a formatter's class chain."""
    class_expr = formatter.get("attributes", {}).get("class")
    if not isinstance(class_expr, str):
        return None
    calculated = "indexOf(@currentField," in class_expr.replace(", ", ",")
    chain = class_expr.removesuffix(_SEVERITY_TEXT_SUFFIX)
    value_map: dict[str, str] = {}
    for match in _ARM.finditer(chain):
        value = match.group(1) if match.group(1) is not None else match.group(2)
        token = _TOKEN_BY_CLASSES.get(match.group(3))
        if value is None or token is None:
            # A class this tool never emits, so the formatter was not
            # generated from a style spec. Fall through to the raw path.
            return None
        value_map[_unquote(value)] = token
    if not value_map:
        return None
    spec: dict[str, Any] = {"style": "severity", "map": value_map}
    if calculated:
        spec["calculated"] = True
    # `icons: false` drops the leading span; the shape says which was used.
    children = formatter.get("children")
    if isinstance(children, list) and len(children) == 1:
        spec["icons"] = False
    return spec


def _overdue_date_candidate(formatter: dict[str, Any]) -> dict[str, Any] | None:
    """An `overdue-date` spec proposed from a formatter's class expression."""
    class_expr = formatter.get("attributes", {}).get("class")
    if not isinstance(class_expr, str) or "@now" not in class_expr:
        return None
    spec: dict[str, Any] = {"style": "overdue-date"}
    if "indexOf(@currentField, ';#')" in class_expr:
        spec["calculated"] = True
    excluded = re.findall(r"\[\$([A-Za-z_][A-Za-z0-9_]*)\] != '((?:[^']|'')*)'", class_expr)
    if excluded:
        guard_field = excluded[0][0]
        if any(name != guard_field for name, _ in excluded):
            # A guard over two different columns is not a shape the style
            # can express, so this formatter was hand-written.
            return None
        spec["guard"] = {
            "field": guard_field,
            "not": [_unquote(value) for _, value in excluded],
        }
    return spec


def invert_column_formatting(
    raw_formatter: str, context: str,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Recover a style spec from a stored `CustomFormatter`.

    Returns `(spec, parsed_formatter)`. `spec` is `None` when no candidate
    reproduced the observed JSON, in which case the caller preserves
    `parsed_formatter` as a raw formatter file. `parsed_formatter` is `None`
    only when the stored value is not JSON at all.
    """
    try:
        observed = json.loads(raw_formatter)
    except (TypeError, ValueError):
        return None, None
    if not isinstance(observed, dict):
        return None, None

    # `pill` is deliberately not proposed: its classes come from a table
    # private to `styles.py`, and copying them here is how the copy and the
    # original come to disagree. A pill formatter is preserved raw, which
    # is faithful, and the notes say the style spec was not recovered.
    candidates = [_severity_candidate(observed), _overdue_date_candidate(observed)]
    target = _canonical(observed)
    for candidate in candidates:
        if candidate is None:
            continue
        try:
            expanded = expand_style(candidate, context)
        except (ValueError, KeyError, TypeError):
            continue
        if _canonical(expanded) == target:
            return candidate, observed
    return None, observed


# === Conditions =============================================================


def _expression_leaf(text: str) -> dict[str, Any] | None:
    """One `[$Col] <op> 'value'` comparison, as an authored condition leaf."""
    text = text.strip()
    for spelling, op in sorted(_EXPR_OPS.items(), key=lambda pair: -len(pair[0])):
        head, sep, tail = text.partition(f" {spelling} ")
        if not sep:
            continue
        ref = _EXPR_REF.fullmatch(head.strip())
        if ref is None:
            return None
        literal = tail.strip()
        if literal.startswith("'") and literal.endswith("'") and len(literal) >= 2:
            value: Any = _unquote(literal[1:-1])
        else:
            return None
        return {"field": ref.group(1), "op": op, "value": value}
    return None


def _split_top_level(text: str, separator: str) -> list[str]:
    """Split on a separator that is not inside brackets or a string literal."""
    parts: list[str] = []
    depth = 0
    in_string = False
    index = 0
    start = 0
    while index < len(text):
        char = text[index]
        if in_string:
            in_string = char != "'"
        elif char == "'":
            in_string = True
        elif char in "([":
            depth += 1
        elif char in ")]":
            depth -= 1
        elif depth == 0 and text.startswith(separator, index):
            parts.append(text[start:index])
            index += len(separator)
            start = index
            continue
        index += 1
    parts.append(text[start:])
    return parts


def _expression_condition(text: str) -> list[dict[str, Any]] | dict[str, Any] | None:
    """An authored `when:` proposed from a rendered expression predicate."""
    text = text.strip()
    if text.startswith("(") and text.endswith(")"):
        inner = text[1:-1]
        if _split_top_level(inner, ")") == [inner]:
            text = inner
    for separator, kind in ((" && ", "all_of"), (" || ", "any_of")):
        parts = _split_top_level(text, separator)
        if len(parts) > 1:
            leaves: list[dict[str, Any]] = []
            for part in parts:
                leaf = _expression_leaf(part)
                if leaf is None:
                    return None
                leaves.append(leaf)
            return [{kind: leaves}] if kind == "any_of" else leaves
    leaf = _expression_leaf(text)
    return [leaf] if leaf is not None else None


def invert_form_visibility(
    formula: str, types: dict[str, str], context: str,
) -> dict[str, Any] | None:
    """Recover a `form_visibility` declaration from a stored formula.

    Verified by re-composing: a candidate is returned only when
    `compose_visibility` renders it back to the observed string exactly.
    """
    text = formula.strip()
    match = re.fullmatch(r"=if\((.*), 'true', 'false'\)", text, re.DOTALL)
    if match is None:
        return None
    body = match.group(1).strip()

    # `true` is the default for both forms, so a recovered declaration only
    # spells the flag it turns off. That is how the shipped mappings are
    # authored, and an extracted one should be diffable against them.
    new, existing = True, True
    gated_only = False
    for gate, gated in ((_EXISTING_ONLY, "existing"), (_NEW_ONLY, "new")):
        if body == gate:
            new, existing, gated_only = gated == "new", gated == "existing", True
            break
        prefix = f"{gate} && "
        if body.startswith(prefix):
            new, existing = gated == "new", gated == "existing"
            body = body[len(prefix):].strip()
            break
    if body == "false":
        new = existing = False
        gated_only = True

    declared: dict[str, Any] = {}
    if not new:
        declared["new"] = False
    if not existing:
        declared["existing"] = False
    when = None
    if not gated_only:
        when = _expression_condition(body)
        if when is None:
            return None
        declared["when"] = when
    return _verified_visibility(declared, when, types, formula, context)


def _verified_visibility(
    declared: dict[str, Any],
    when: object,
    types: dict[str, str],
    observed: str,
    context: str,
) -> dict[str, Any] | None:
    condition: Condition | None = None
    if when is not None:
        try:
            condition = parse_condition(when, context)
        except (ValueError, KeyError, TypeError):
            return None
    try:
        rendered = compose_visibility(
            new=declared.get("new", True),
            existing=declared.get("existing", True),
            when=condition,
            types=types,
        )
    except (ValueError, KeyError, TypeError):
        return None
    return declared if rendered == observed.strip() else None


_SAVE_INSTANT = re.compile(r"^\[?Modified\]?$", re.IGNORECASE)
# The columns that carry a time of day; one home in condition_rendering too.
_DATETIME_TYPES = frozenset({"datetime"})
_SHIFTED_REF = re.compile(r"^(?P<ref>.+?)(?P<shift>[+-]\d+)?$")


def _save_instant_leaf(
    head: str, op: str, tail: str, types: dict[str, str],
) -> dict[str, Any] | None:
    """A comparison against `[Modified]`, the save instant, back to the
    `today`/`now` sentinel the build rendered it from (see
    `analysis/condition_rendering._save_instant_leaf`).

    A datetime compares directly, so the sentinel is `now`. A date-only
    column is shifted by whole days on the column side, so `D-N<=Modified`
    is `leq today+N` and `D+1<=Modified` is `lt today`, which comes back in
    its equivalent canonical spelling `leq today-1`: the two render to the
    same formula, and the canonical one is what a re-read compares equal to.
    """
    if not _SAVE_INSTANT.match(tail.strip()):
        return None
    shifted = _SHIFTED_REF.fullmatch(head.strip())
    if shifted is None:
        return None
    ref = re.fullmatch(_VALIDATION_REF, shifted.group("ref").strip())
    if ref is None:
        return None
    name = ref.group("braced") or ref.group("bare")
    column_type = types.get(name)
    if column_type is None or column_type not in DATE_TYPES:
        return None
    shift = int(shifted.group("shift") or 0)
    if column_type in _DATETIME_TYPES:
        return None if shift else {"field": name, "op": op, "value": "now"}
    if op not in ("leq", "gt"):
        return None
    offset = -shift
    value = "today" if offset == 0 else f"today{offset:+d}"
    return {"field": name, "op": op, "value": value}


def _validation_leaf(text: str, types: dict[str, str]) -> dict[str, Any] | None:
    """One comparison from a validation formula, as an authored leaf.

    SharePoint stores these normalised: brackets it does not need are
    stripped, whitespace is removed, and a display-name reference is
    resolved to the internal name. So both `[Last Reviewed Date]<=TODAY()`
    and `LastReviewedDate<=TODAY()` have to reach the same leaf.
    """
    for spelling, op in _VALIDATION_OPS:
        head, sep, tail = text.partition(spelling)
        if not sep:
            continue
        against_save = _save_instant_leaf(head, op, tail, types)
        if against_save is not None:
            return against_save
        ref = re.fullmatch(_VALIDATION_REF, head.strip())
        if ref is None:
            continue
        name = ref.group("braced") or ref.group("bare")
        if name not in types:
            continue
        value = _validation_operand(tail.strip(), types[name])
        if value is None:
            continue
        return {"field": name, "op": op, "value": value}
    return None


def _validation_operand(text: str, column_type: str) -> Any:
    """A validation formula's right-hand side, as an authored value."""
    if text.upper() in ("TODAY()", "NOW()"):
        return text.upper().removesuffix("()").lower()
    if text.startswith('"') and text.endswith('"') and len(text) >= 2:
        return text[1:-1].replace('""', '"')
    if column_type in NUMBER_TYPES:
        try:
            return int(text) if "." not in text else float(text)
        except ValueError:
            return None
    return None


def invert_column_validation(
    formula: str, message: str, types: dict[str, str], context: str,
) -> dict[str, Any] | None:
    """Recover a `column_validation` declaration from a stored rule.

    Only a single comparison is attempted. Anything else is reported as
    unrecovered rather than approximated, because `column_validation` has
    no raw-formula escape hatch: a wrong inversion would be deployed as a
    save rule that refuses the wrong rows.
    """
    body = formula.strip().removeprefix("=").strip()
    leaf = _validation_leaf(body, types)
    if leaf is None:
        return None
    declared = {"when": [leaf], "message": message}
    try:
        condition = parse_condition(declared["when"], context)
        rendered = f"={to_validation(condition, types)}"
    except (ValueError, KeyError, TypeError):
        return None
    if _canonical_validation(rendered) != _canonical_validation(formula):
        return None
    return declared


def _canonical_validation(formula: str) -> str:
    """Compare validation formulas the way the deploy already has to.

    `templates/deploy/_field_reconcile.js.j2` records the storage
    normalisation this undoes, live-verified: brackets that do not need
    delimiting are stripped and whitespace is removed. Bracket text inside
    a string literal is data, so it is left alone.
    """
    out = []
    for index, part in enumerate(re.split(r'("(?:""|[^"])*")', formula)):
        if index % 2 == 1:
            out.append(part)
            continue
        collapsed = re.sub(r"\s+", "", part)
        out.append(re.sub(r"\[([A-Za-z0-9_]+)\]", r"\1", collapsed))
    return "".join(out)


def rendered_expression(when: object, types: dict[str, str], context: str) -> str | None:
    """Render an authored condition, or `None` if it will not render.

    Used by the emitter to drop a recovered declaration that the forward
    build would refuse, so the emitted mapping is one that actually builds.
    """
    try:
        return to_expression(parse_condition(when, context), types)
    except (ValueError, KeyError, TypeError):
        return None
