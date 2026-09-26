# src/dbml_sharepoint/analysis/styles.py
"""The fleet style standard: semantic tokens + parameterised column styles.

Tokens resolve to SharePoint's OWN documented formatting classes (the
sp-field-severity--* set plus sanctioned Fluent UI background classes)
with the Learn reference's canonical Fluent icon pairings, never raw
hexes. Styles expand at mapping-load time into plain SP formatter JSON,
so the validator, jsgen and the deploy machinery see ordinary formatters.
Reference:
https://learn.microsoft.com/en-us/sharepoint/dev/declarative-customization/column-formatting
(style guidelines; conditional formatting / data bar / trending / date
examples; the emitted structures mirror those samples).
"""

import math
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

# The finding codes the registry names; `findings` imports only the standard
# library, so there is no cycle.
from dbml_sharepoint.analysis.findings import FindingCode
from dbml_sharepoint.analysis.formatter_values import ScalarValue, hide_blank, quoted, text_value
from dbml_sharepoint.analysis.typemap import DATE_TYPES, NUMBER_TYPES

# The unknown-key guard, imported rather than reimplemented.
#
# A style spec used to ignore everything it did not recognise, and every miss
# was silent and wrong in the direction that reads as fine: a typo'd `guard:`
# renders finished rows as overdue, and `calculated: true` -- documented as
# required on a calculated column -- changed nothing at all when misspelled,
# so the values kept their `string;#` prefix and matched no map key.
#
# The fix at the time was a SECOND COPY of `model/_keys._reject_unknown_keys`,
# emitting byte-identical text (`_fail` composes `"{context}: {message}"`,
# which is exactly what the original produced) while omitting its `isinstance`
# guard. Same rule, same kind of block, so it is now the same function -- and
# style specs pick up the mapping check they were missing.
#
# `model/` stays the home even though this is `analysis/`: `_keys.py` imports
# nothing but `typing`, so there is no cycle, and every other caller of the
# guard is a parser under `model/`.
from dbml_sharepoint.model._keys import _reject_unknown_keys

# Same route as the guard above, and the same reason: `_formatting.read`
# delegates to this module, so a refusal here is a mapping refusal.
from dbml_sharepoint.model.errors import MappingShapeError, MappingValueError
from dbml_sharepoint.model.reading import optional_value

_SCHEMA = "https://developer.microsoft.com/json-schemas/sp/v2/column-formatting.schema.json"


@dataclass(frozen=True)
class StyleToken:
    classes: str
    icon: str | None


TOKENS: dict[str, StyleToken] = {
    "good": StyleToken("sp-field-severity--good", "CheckMark"),
    "low": StyleToken("sp-field-severity--low", "Forward"),
    "warning": StyleToken("sp-field-severity--warning", "Error"),
    "severe": StyleToken("sp-field-severity--severeWarning", "Warning"),
    "blocked": StyleToken("sp-field-severity--blocked", "ErrorBadge"),
    # Background-only Fluent classes; the severity structure appends the
    # doc's ms-fontColor-neutralSecondary for text.
    "neutral": StyleToken("ms-bgColor-neutralLighter", None),
    "muted": StyleToken("ms-bgColor-neutralLight", None),
}

# Compact native choice-pill class pairs (the opt-in `pill` style).
# BgDustRose/BgGold are live-verified on tenant (row-extreme.json).
_PILL_CLASSES: dict[str, str] = {
    "good": "sp-css-backgroundColor-BgMintGreen sp-css-color-MintGreenFont",
    "low": "sp-css-backgroundColor-BgCornflowerBlue sp-css-color-CornflowerBlueFont",
    "warning": "sp-css-backgroundColor-BgGold sp-css-color-GoldFont",
    "severe": "sp-css-backgroundColor-BgPeach sp-css-color-PeachFont",
    "blocked": "sp-css-backgroundColor-BgDustRose sp-css-color-DustRoseFont",
    "neutral": "ms-bgColor-neutralLighter ms-fontColor-neutralPrimary",
    "muted": "ms-bgColor-neutralLight ms-fontColor-neutralSecondary",
}

# Keep adjacent filled cells visually separate.
_CELL_INSET: dict[str, str] = {"border-radius": "4px", "margin": "1px 4px 1px 0"}

def _fail(context: str, message: str) -> MappingShapeError:
    """A spec that is not the shape its expander reads: a key absent, or a
    value of the wrong YAML type."""
    return MappingShapeError(f"{context}: {message}")

def _not_in_vocabulary(context: str, message: str) -> MappingValueError:
    """A spec naming a style or a token this module does not define.

    The same sentence as `_fail`, with the class the loader's split gives a
    word outside a closed set rather than a shape.
    """
    return MappingValueError(f"{context}: {message}")


# SP resolves `[$Name]` against a column's INTERNAL name; anything else
# resolves to no column and renders as nothing. Same character class
# `column_refs._FORMATTER_FIELD_REF` extracts, still written out rather than
# imported because the two have diverged: that one extracts, this one
# validates with `fullmatch`, and merging them is a separate judgment.
# Measured not stronger than what we ship: all 634 declared column names
# match it.
#: Matched with `fullmatch`. Anchored with `$`, a name ending in a newline
#: was accepted and emitted a reference the validator then read as valid.
_INTERNAL_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

def _internal_name(value: object, context: str, message: str) -> str:
    """Read a spec value that becomes a `[$Name]` column reference."""
    if not isinstance(value, str) or not _INTERNAL_NAME.fullmatch(value):
        raise _fail(context, message)
    return value

def _bool(spec: dict[str, Any], key: str, context: str, *, default: bool) -> bool:
    """Read a style-spec boolean without truthiness-coercing bad YAML.

    `bool("false")` is True, so the cautious spelling meant its opposite:
    `calculated: "false"` switched the calculated-value handling ON, and
    `icons: "false"` kept the icons it was written to remove.

    A blank key takes `default` and is recorded, the rule `model/reading.py` states.
    """
    value = optional_value(spec, key, context, default=default)
    if not isinstance(value, bool):
        raise _fail(context, f"{key}: expected true or false, got {value!r}")
    return value

def _resolve(
    token_name: str, context: str, theme: dict[str, StyleToken] | None,
) -> StyleToken:
    if theme and token_name in theme:
        return theme[token_name]
    token = TOKENS.get(token_name)
    if token is None:
        raise _not_in_vocabulary(
            context, f"unknown token {token_name!r} (known: {sorted(TOKENS)})",
        )
    return token

def _if_chain(pairs: list[tuple[str, str]], fallback: str) -> str:
    """Excel-style nested =if(...) expression over (condition, quoted-value)."""
    expr = quoted(fallback)
    for condition, value in reversed(pairs):
        expr = f"if({condition}, {quoted(value)}, {expr})"
    return "=" + expr

def _validated_map(spec: dict[str, Any], context: str) -> dict[str, str]:
    """The `map` of column value to token name.

    A value is stringified because a cell is compared as text and YAML reads
    `1` or `true` as a scalar. A TOKEN is not: `str()` on a list made
    `map: {Open: [good]}` report the unknown token `"['good']"`, a word
    outside the vocabulary where the real fault is the shape.
    """
    raw_map = spec.get("map")
    if not isinstance(raw_map, dict) or not raw_map:
        raise _fail(context, "this style requires a non-empty 'map' of value -> token")
    value_map: dict[object, object] = raw_map
    tokens: dict[str, str] = {}
    for value, token in value_map.items():
        if not isinstance(token, str):
            raise _fail(context, f"map[{value!r}] must be a token name, got {token!r}")
        tokens[str(value)] = token
    return tokens

def _condition(value: str, calculated: bool, ref: str = "@currentField") -> str:
    source = text_value(ref, calculated=True) if calculated else ref
    return f"{source} == {quoted(value)}"


#: The nested key sets, named so the registry publishes the same objects the
#: expanders enforce and the two cannot drift apart.
_COLOR_BY_KEYS = frozenset({"field", "map", "calculated"})
_GUARD_KEYS = frozenset({"field", "not"})

def _severity(
    spec: dict[str, Any], context: str, theme: dict[str, StyleToken] | None,
) -> dict[str, Any]:
    value_map = _validated_map(spec, context)
    calculated = _bool(spec, "calculated", context, default=False)
    icons = _bool(spec, "icons", context, default=True)
    tokens = {v: _resolve(t, context, theme) for v, t in value_map.items()}
    fallback = _resolve("muted", context, theme)
    return _severity_cell(
        [(_condition(v, calculated), tok) for v, tok in tokens.items()], fallback,
        "=" + text_value(calculated=calculated),
        text_value(calculated=calculated), icons=icons,
    )

def _severity_cell(
    pairs: list[tuple[str, StyleToken]], fallback: StyleToken,
    label: str, text: str, *, icons: bool,
) -> dict[str, Any]:
    """One layout and token-to-icon mapping for categorical and numeric severity."""
    children: list[dict[str, Any]] = []
    if icons:
        children.append({
            "elmType": "span",
            "style": {"display": "inline-block", "padding": "0 4px"},
            "attributes": {"iconName": _if_chain(
                [(condition, token.icon or "") for condition, token in pairs],
                fallback.icon or "",
            )},
        })
    children.append({"elmType": "span", "txtContent": label})
    return {
        "$schema": _SCHEMA,
        "elmType": "div",
        "style": {"display": hide_blank(text), **_CELL_INSET},
        "attributes": {"class": _if_chain(
            [(condition, token.classes) for condition, token in pairs], fallback.classes,
        ) + " + ' ms-fontColor-neutralSecondary'"},
        "children": children,
    }

def _finite_number(value: object, context: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise _fail(context, "expected a finite number")
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise _fail(context, "expected a finite number")
    return value

def _numeric_severity(
    spec: dict[str, Any], context: str, theme: dict[str, StyleToken] | None,
) -> dict[str, Any]:
    bands = spec.get("bands")
    if not isinstance(bands, list) or not bands:
        raise _fail(context, "numeric-severity requires non-empty bands")
    otherwise = spec.get("otherwise")
    if not isinstance(otherwise, str):
        raise _fail(context, "numeric-severity requires an otherwise token")
    fallback = _resolve(otherwise, context, theme)
    value = ScalarValue("Number", calculated=_bool(spec, "calculated", context, default=False))
    pairs: list[tuple[str, StyleToken]] = []
    previous: int | float | None = None
    for band in bands:
        if not isinstance(band, dict):
            raise _fail(context, "each band must be a mapping")
        _reject_unknown_keys(band, frozenset({"max", "token"}), context)
        maximum = _finite_number(band.get("max"), context)
        if previous is not None and maximum <= previous:
            raise _fail(context, "band maxima must be strictly increasing")
        previous = maximum
        token = band.get("token")
        if not isinstance(token, str):
            raise _fail(context, "each band requires a token")
        pairs.append((f"{value.valid} && {value.value} <= {maximum}",
                      _resolve(token, context, theme)))
    pairs.append((value.valid, fallback))
    return _severity_cell(
        pairs, _resolve("muted", context, theme), value.label, value.text,
        icons=_bool(spec, "icons", context, default=True),
    )


def _pill(
    spec: dict[str, Any], context: str, theme: dict[str, StyleToken] | None,
) -> dict[str, Any]:
    value_map = _validated_map(spec, context)
    for token_name in value_map.values():
        if theme and token_name in theme:
            continue
        if token_name not in _PILL_CLASSES:
            raise _not_in_vocabulary(
                context,
                f"unknown token {token_name!r} (known: {sorted(_PILL_CLASSES)})",
            )
    pairs = [
        (_condition(v, False),
         theme[t].classes if theme and t in theme else _PILL_CLASSES[t])
        for v, t in value_map.items()
    ]
    return {
        "$schema": _SCHEMA,
        "elmType": "div",
        "style": {
            "display": hide_blank(text_value(), "inline-flex"),
            "padding": "2px 10px",
            "border-radius": "12px",
            "font-weight": "600",
        },
        "attributes": {"class": _if_chain(pairs, _PILL_CLASSES["muted"])},
        "children": [{"elmType": "span", "txtContent": "@currentField"}],
    }

def _data_bar(
    spec: dict[str, Any], context: str, theme: dict[str, StyleToken] | None,
) -> dict[str, Any]:
    maximum = spec.get("max")
    if not isinstance(maximum, int) or isinstance(maximum, bool) or maximum <= 0:
        raise _fail(context, "data-bar requires a positive integer 'max'")
    _finite_number(maximum, context)
    factor_text = f"{100 / maximum:g}"
    target_calculated = _bool(spec, "calculated", context, default=False)
    scalar = ScalarValue("Number", calculated=target_calculated)
    value = scalar.value
    color_by = spec.get("color_by")
    if color_by is None:
        class_expr = "sp-field-dataBars"
    else:
        # Mapping translation: the bar keeps its width semantics but takes
        # its fill from the severity token mapped from ANOTHER column's
        # value, so a score bar wears the same standardised colours as the
        # rating column beside it. The native sp-field-dataBars class is
        # dropped. Its fixed theme fill would fight the conditional one.
        if not isinstance(color_by, dict):
            raise _fail(context, "color_by must be a mapping with 'field' and 'map'")
        field_name = _internal_name(
            color_by.get("field"),
            context,
            "color_by requires 'field' (a column internal name)",
        )
        _reject_unknown_keys(color_by, _COLOR_BY_KEYS, f"{context}.color_by")
        value_map = _validated_map(color_by, context)
        source_calculated = _bool(
            color_by, "calculated", f"{context}.color_by", default=False,
        )
        tokens = {v: _resolve(t, context, theme) for v, t in value_map.items()}
        fallback = _resolve("muted", context, theme)
        ref = f"[${field_name}]"
        pairs = [
            (_condition(v, source_calculated, ref), tok.classes)
            for v, tok in tokens.items()
        ]
        class_expr = (
            _if_chain(pairs, fallback.classes)
            + " + ' ms-fontColor-neutralSecondary'"
        )
    fill = quoted(class_expr) if not class_expr.startswith("=") else class_expr[1:]
    return {
        "$schema": _SCHEMA,
        "elmType": "div",
        "children": [{
            "elmType": "span",
            "txtContent": scalar.label,
            "style": {"padding-left": "8px", "white-space": "nowrap", "flex-shrink": "0"},
        }],
        "attributes": {"class": f"=if({scalar.valid}, "
                       f"{fill}, "
                       f"{quoted(_resolve('muted', context, theme).classes)})"},
        "style": {
            "padding": "0",
            "display": hide_blank(scalar.text),
            "width": (
                f"=if({scalar.valid}, if({value} <= 0, '0%', "
                f"if({value} >= {maximum}, '100%', "
                f"({value} * {factor_text}) + '%')), '100%')"
            ),
            **_CELL_INSET,
        },
    }

def _trend(
    spec: dict[str, Any], context: str, theme: dict[str, StyleToken] | None,
) -> dict[str, Any]:
    against = spec.get("against")
    wanted = "trend requires 'against' (a column internal name or a number)"
    calculated_against = _bool(spec, "against_calculated", context, default=False)
    if isinstance(against, str):
        ref = f"[${_internal_name(against, context, wanted)}]"
    else:
        ref = str(_finite_number(against, context))
        if calculated_against:
            raise _fail(context, "against_calculated requires a column reference")
    value = ScalarValue("Number", calculated=_bool(spec, "calculated", context, default=False))
    baseline = ScalarValue("Number", ref, calculated_against)
    valid = f"{value.valid} && {baseline.valid}"
    up = f"{valid} && {value.value} > {baseline.value}"
    down = f"{valid} && {value.value} < {baseline.value}"
    return {
        "$schema": _SCHEMA,
        "elmType": "div",
        "style": {"display": hide_blank(value.text)},
        "children": [
            {"elmType": "span", "attributes": {
                "class": _if_chain([(up, "sp-field-trending--up"),
                                    (down, "sp-field-trending--down")], ""),
                "iconName": _if_chain([(up, "SortUp"), (down, "SortDown")], ""),
            }},
            {"elmType": "span", "txtContent": value.label},
        ],
    }


def _overdue_date(
    spec: dict[str, Any], context: str, theme: dict[str, StyleToken] | None,
) -> dict[str, Any]:
    calculated = _bool(spec, "calculated", context, default=False)
    scalar = ScalarValue("Date", calculated=calculated)
    value = scalar.value
    guard = spec.get("guard")
    guard_terms = ""
    if guard is not None:
        if not isinstance(guard, dict):
            raise _fail(context, "overdue-date guard must be a mapping")
        guard_map: dict[object, object] = guard
        _reject_unknown_keys(guard_map, _GUARD_KEYS, f"{context}.guard")
        field_name = _internal_name(
            guard_map.get("field"),
            context,
            "overdue-date guard requires 'field' (a column internal name)",
        )
        # A string is iterable, so `or []` sent "Done" through as four
        # single-character comparisons. A blank `not:` excludes nothing.
        raw_excluded = guard_map.get("not")
        if raw_excluded is None:
            raw_excluded = list[object]()
        if not isinstance(raw_excluded, list):
            raise _fail(context, "overdue-date guard 'not' must be a list of values")
        excluded: list[object] = raw_excluded
        guard_terms = "".join(
            f" && [${field_name}] != {quoted(str(v))}"
            for v in excluded
        )
    overdue = f"{scalar.valid} && {value} < @now{guard_terms}"
    severe = _resolve("severe", context, theme)
    return {
        "$schema": _SCHEMA,
        "elmType": "div",
        "style": {"display": hide_blank(scalar.text), **_CELL_INSET},
        "attributes": {
            "class": (
                f"=if({overdue}, "
                f"'{severe.classes} ms-fontColor-neutralSecondary', "
                f"if({scalar.valid}, '', {quoted(_resolve('muted', context, theme).classes)}))"
            ),
        },
        "children": [
            {
                "elmType": "span",
                "style": {"display": "inline-block", "padding": "0 4px"},
                "attributes": {
                    "iconName": f"=if({overdue}, '{severe.icon or ''}', '')",
                },
            },
            {"elmType": "span", "txtContent": scalar.label},
        ],
    }


type Expander = Callable[
    [dict[str, Any], str, dict[str, StyleToken] | None], dict[str, Any],
]


@dataclass(frozen=True)
class ValueMapRule:
    """A `map:` of column value to token, and the column whose enum its keys must belong to."""

    at: tuple[str, ...]      # () for the spec's own map, ("color_by",) for a nested one
    source_key: str | None   # None: the styled column. Otherwise the key naming the source column.
    code: FindingCode
    label: str               # "map key" or "color_by map key", as the message spells it


@dataclass(frozen=True)
class ColumnRefRule:
    """A spec value that must name a rendered column of the same list."""

    at: tuple[str, ...]      # () or ("guard",)
    key: str                 # "against" or "field"
    code: FindingCode
    message: str             # str.format template over {name!r} and {entity}


@dataclass(frozen=True)
class StyleSpec:
    """Everything the validator needs to know about one style, beside its expander."""

    expand: Expander
    keys: frozenset[str]
    nested_keys: dict[tuple[str, ...], frozenset[str]] = field(default_factory=dict)
    calculated_type: str | None = None
    target_types: frozenset[str] = frozenset()
    scalar_refs: tuple[tuple[str, str], ...] = ()
    literal_match: bool = False   # compares @currentField against quoted literals
    value_maps: tuple[ValueMapRule, ...] = ()
    column_refs: tuple[ColumnRefRule, ...] = ()


#: severity and pill share one rule: the styled column's own map keys.
_SEVERITY_MAP = ValueMapRule((), None, FindingCode.STYLE_MAP_KEY_NOT_IN_ENUM, "map key")

#: Every style there is. Insertion order is the order `expand_style` lists in
#: its unknown-style message, so a style added here is offered to the author.
STYLES: dict[str, StyleSpec] = {
    "severity": StyleSpec(
        expand=_severity,
        keys=frozenset({"style", "map", "calculated", "icons"}),
        calculated_type="calculated_text",
        literal_match=True,
        value_maps=(_SEVERITY_MAP,),
    ),
    "numeric-severity": StyleSpec(
        expand=_numeric_severity,
        keys=frozenset({"style", "bands", "otherwise", "calculated", "icons"}),
        calculated_type="calculated_number",
        target_types=NUMBER_TYPES,
    ),
    "pill": StyleSpec(
        expand=_pill,
        keys=frozenset({"style", "map"}),
        literal_match=True,
        value_maps=(_SEVERITY_MAP,),
    ),
    "data-bar": StyleSpec(
        expand=_data_bar,
        keys=frozenset({"style", "max", "calculated", "color_by"}),
        nested_keys={("color_by",): _COLOR_BY_KEYS},
        calculated_type="calculated_number",
        target_types=NUMBER_TYPES,
        value_maps=(
            ValueMapRule(
                ("color_by",), "field", FindingCode.COLOR_BY_MAP_KEY_NOT_IN_ENUM,
                "color_by map key",
            ),
        ),
    ),
    "trend": StyleSpec(
        expand=_trend,
        scalar_refs=(("against", "against_calculated"),),
        keys=frozenset({"style", "against", "calculated", "against_calculated"}),
        calculated_type="calculated_number",
        target_types=NUMBER_TYPES,
        column_refs=(
            ColumnRefRule(
                (), "against", FindingCode.TREND_AGAINST_NOT_RENDERED,
                "trend 'against' references {name!r}, which is not a rendered column of {entity}.",
            ),
        ),
    ),
    "overdue-date": StyleSpec(
        expand=_overdue_date,
        keys=frozenset({"style", "calculated", "guard"}),
        nested_keys={("guard",): _GUARD_KEYS},
        calculated_type="calculated_date",
        target_types=DATE_TYPES,
        column_refs=(
            ColumnRefRule(
                ("guard",), "field", FindingCode.OVERDUE_GUARD_FIELD_NOT_RENDERED,
                "guard field {name!r} is not a rendered column of {entity}.",
            ),
        ),
    ),
}

def expand_style(
    spec: dict[str, Any],
    context: str,
    theme: dict[str, StyleToken] | None = None,
) -> dict[str, Any]:
    """Expand a declared style spec into plain SP column-formatting JSON."""
    style = spec.get("style")
    # The shape before the word, the split the loader draws everywhere else:
    # `style: []` is not a style name this module declines to know.
    if not isinstance(style, str):
        raise _fail(context, f"'style' must be a string, got {style!r}")
    registered = STYLES.get(style)
    if registered is None:
        raise _not_in_vocabulary(
            context, f"unknown style {style!r} (known: {list(STYLES)})",
        )
    # Hoisted from the five expanders, which each opened with it, so the same
    # failure still wins.
    _reject_unknown_keys(spec, registered.keys, context)
    return registered.expand(spec, context, theme)

def _theme_classes(raw: object, name: str, context: str) -> str:
    """A token override's `classes`: one string, or a list of class names
    joined by spaces."""
    classes = raw
    if isinstance(raw, list):
        listed: list[object] = raw
        class_names: list[str] = []
        for member in listed:
            # `str()` on a list member emitted the class "['a', 'b']", as it did for `icon`.
            if not isinstance(member, str):
                raise _fail(
                    context, f"{name}: 'classes' members must be strings, got {member!r}",
                )
            class_names.append(member)
        classes = " ".join(class_names)
    if not isinstance(classes, str) or not classes:
        raise _fail(
            context, f"{name}: 'classes' (non-empty list or string) is required",
        )
    return classes

def parse_theme(raw: object, context: str) -> dict[str, StyleToken]:
    """Parse the optional mapping-level style_theme key: per-token
    overrides {token: {classes: [...] | str, icon: str|null}}."""
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise _fail(context, "expected a mapping of token overrides")
    overrides: dict[object, object] = raw
    theme: dict[str, StyleToken] = {}
    for name, override in overrides.items():
        # The shape before the word here too: a YAML key may be any scalar,
        # and `1` is not a token name spelled wrongly.
        if not isinstance(name, str):
            raise _fail(context, f"token name must be a string, got {name!r}")
        if name not in TOKENS:
            raise _not_in_vocabulary(
                context, f"unknown token {name!r} (known: {sorted(TOKENS)})",
            )
        if not isinstance(override, dict):
            raise _fail(context, f"{name}: expected a mapping with classes/icon")
        override_map: dict[object, object] = override
        _reject_unknown_keys(override_map, {"classes", "icon"}, f"{context}.{name}")
        classes = _theme_classes(override_map.get("classes"), name, context)
        # An absent `icon` keeps the token's own and `icon: null` is a
        # declared no icon; `str()` on anything else emitted "['Emoji2']".
        icon = override_map.get("icon", TOKENS[name].icon)
        if icon is not None and not isinstance(icon, str):
            raise _fail(context, f"{name}: 'icon' must be a string or null, got {icon!r}")
        theme[name] = StyleToken(classes, icon)
    return theme
