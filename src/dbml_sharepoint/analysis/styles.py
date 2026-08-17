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

import re
from dataclasses import dataclass
from typing import Any

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

_HIDE_BLANK = "=if(@currentField == '', 'none', 'flex')"
# Cell inset shared by every filled style: adjacent same-coloured fills
# (e.g. a blocked-red score bar beside a blocked-red rating cell) blend
# into one block without it. The radius + right/vertical gap makes each
# cell read as its own element.
_CELL_INSET: dict[str, str] = {"border-radius": "4px", "margin": "1px 4px 1px 0"}
# SP renders calculated-text values as 'string;#Value'; strip for display.
_CALC_TEXT = (
    "=if(indexOf(@currentField, ';#') >= 0, "
    "substring(@currentField, indexOf(@currentField, ';#') + 2, 1000), "
    "@currentField)"
)


def _calculated_scalar(constructor: str) -> str:
    """Decode SharePoint's ``type;#value`` calculated-field payload."""
    return (
        f"{constructor}(substring(@currentField, "
        "indexOf(@currentField, ';#') + 2, 1000))"
    )


def _fail(context: str, message: str) -> ValueError:
    return ValueError(f"{context}: {message}")


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
    """
    value = spec.get(key, default)
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
        raise _fail(context, f"unknown token {token_name!r} (known: {sorted(TOKENS)})")
    return token


def _if_chain(pairs: list[tuple[str, str]], fallback: str) -> str:
    """Excel-style nested =if(...) expression over (condition, quoted-value)."""
    expr = f"'{fallback}'"
    for condition, value in reversed(pairs):
        expr = f"if({condition}, '{value}', {expr})"
    return "=" + expr


def _validated_map(spec: dict[str, Any], context: str) -> dict[str, str]:
    value_map = spec.get("map")
    if not isinstance(value_map, dict) or not value_map:
        raise _fail(context, "this style requires a non-empty 'map' of value -> token")
    return {str(value): str(token) for value, token in value_map.items()}


def _condition(value: str, calculated: bool, ref: str = "@currentField") -> str:
    escaped = value.replace("'", "''")
    if calculated:
        return f"indexOf({ref}, '{escaped}') >= 0"
    return f"{ref} == '{escaped}'"


def _severity(
    spec: dict[str, Any], context: str, theme: dict[str, StyleToken] | None,
) -> dict[str, Any]:
    _reject_unknown_keys(spec, {"style", "map", "calculated", "icons"}, context)
    value_map = _validated_map(spec, context)
    calculated = _bool(spec, "calculated", context, default=False)
    icons = _bool(spec, "icons", context, default=True)
    tokens = {v: _resolve(t, context, theme) for v, t in value_map.items()}
    fallback = _resolve("muted", context, theme)
    class_pairs = [
        (_condition(v, calculated), tok.classes) for v, tok in tokens.items()
    ]
    class_expr = (
        _if_chain(class_pairs, fallback.classes)
        + " + ' ms-fontColor-neutralSecondary'"
    )
    text_span: dict[str, Any] = {
        "elmType": "span",
        "txtContent": _CALC_TEXT if calculated else "@currentField",
    }
    children: list[dict[str, Any]] = []
    if icons:
        icon_pairs = [
            (_condition(v, calculated), tok.icon or "") for v, tok in tokens.items()
        ]
        children.append({
            "elmType": "span",
            "style": {"display": "inline-block", "padding": "0 4px"},
            "attributes": {"iconName": _if_chain(icon_pairs, fallback.icon or "")},
        })
    children.append(text_span)
    return {
        "$schema": _SCHEMA,
        "elmType": "div",
        "style": {"display": _HIDE_BLANK, **_CELL_INSET},
        "attributes": {"class": class_expr},
        "children": children,
    }


def _pill(
    spec: dict[str, Any], context: str, theme: dict[str, StyleToken] | None,
) -> dict[str, Any]:
    _reject_unknown_keys(spec, {"style", "map"}, context)
    value_map = _validated_map(spec, context)
    for token_name in value_map.values():
        if theme and token_name in theme:
            continue
        if token_name not in _PILL_CLASSES:
            raise _fail(
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
            "display": "=if(@currentField == '', 'none', 'inline-flex')",
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
    _reject_unknown_keys(spec, {"style", "max", "calculated", "color_by"}, context)
    maximum = spec.get("max")
    if not isinstance(maximum, int) or isinstance(maximum, bool) or maximum <= 0:
        raise _fail(context, "data-bar requires a positive integer 'max'")
    factor_text = f"{100 / maximum:g}"
    target_calculated = _bool(spec, "calculated", context, default=False)
    value = _calculated_scalar("Number") if target_calculated else "@currentField"
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
        _reject_unknown_keys(
            color_by, {"field", "map", "calculated"}, f"{context}.color_by",
        )
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
    return {
        "$schema": _SCHEMA,
        "elmType": "div",
        "children": [{
            "elmType": "span",
            "txtContent": f"={value}" if target_calculated else value,
            "style": {"padding-left": "8px", "white-space": "nowrap"},
        }],
        "attributes": {"class": class_expr},
        "style": {
            "padding": "0",
            "display": _HIDE_BLANK,
            "width": (
                f"=if({value} >= {maximum}, '100%', "
                f"({value} * {factor_text}) + '%')"
            ),
            **_CELL_INSET,
        },
    }


def _trend(spec: dict[str, Any], context: str) -> dict[str, Any]:
    _reject_unknown_keys(spec, {"style", "against"}, context)
    against = spec.get("against")
    wanted = "trend requires 'against' (a column internal name or a number)"
    # A column name becomes a reference; a number stays a bare literal. Anything
    # else used to be str()'d into the expression, which compares against junk.
    if isinstance(against, str):
        ref = f"[${_internal_name(against, context, wanted)}]"
    elif isinstance(against, int | float) and not isinstance(against, bool):
        ref = str(against)
    else:
        raise _fail(context, wanted)
    return {
        "$schema": _SCHEMA,
        "elmType": "div",
        "children": [
            {
                "elmType": "span",
                "attributes": {
                    "class": (
                        f"=if(@currentField > {ref}, 'sp-field-trending--up', "
                        f"'sp-field-trending--down')"
                    ),
                    "iconName": (
                        f"=if(@currentField > {ref}, 'SortUp', "
                        f"if(@currentField < {ref}, 'SortDown', ''))"
                    ),
                },
            },
            {"elmType": "span", "txtContent": "@currentField"},
        ],
    }


def _overdue_date(
    spec: dict[str, Any], context: str, theme: dict[str, StyleToken] | None,
) -> dict[str, Any]:
    _reject_unknown_keys(spec, {"style", "calculated", "guard"}, context)
    calculated = _bool(spec, "calculated", context, default=False)
    value = _calculated_scalar("Date") if calculated else "@currentField"
    guard = spec.get("guard")
    guard_terms = ""
    if guard is not None:
        if not isinstance(guard, dict):
            raise _fail(context, "overdue-date guard must be a mapping")
        _reject_unknown_keys(guard, {"field", "not"}, f"{context}.guard")
        field_name = _internal_name(
            guard.get("field"),
            context,
            "overdue-date guard requires 'field' (a column internal name)",
        )
        # A string is iterable, so `or []` sent "Done" through as four
        # single-character comparisons.
        excluded = guard.get("not", [])
        if not isinstance(excluded, list):
            raise _fail(context, "overdue-date guard 'not' must be a list of values")
        guard_terms = "".join(
            f" && [${field_name}] != '{str(v).replace(chr(39), chr(39) * 2)}'"
            for v in excluded
        )
    overdue = f"@currentField != '' && {value} < @now{guard_terms}"
    severe = _resolve("severe", context, theme)
    return {
        "$schema": _SCHEMA,
        "elmType": "div",
        "style": dict(_CELL_INSET),
        "attributes": {
            "class": (
                f"=if({overdue}, "
                f"'{severe.classes} ms-fontColor-neutralSecondary', '')"
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
            {"elmType": "span", "txtContent": f"=toLocaleDateString({value})"},
        ],
    }


_STYLES = ("severity", "pill", "data-bar", "trend", "overdue-date")


def expand_style(
    spec: dict[str, Any],
    context: str,
    theme: dict[str, StyleToken] | None = None,
) -> dict[str, Any]:
    """Expand a declared style spec into plain SP column-formatting JSON."""
    style = spec.get("style")
    if style == "severity":
        return _severity(spec, context, theme)
    if style == "pill":
        return _pill(spec, context, theme)
    if style == "data-bar":
        return _data_bar(spec, context, theme)
    if style == "trend":
        return _trend(spec, context)
    if style == "overdue-date":
        return _overdue_date(spec, context, theme)
    raise _fail(context, f"unknown style {style!r} (known: {list(_STYLES)})")


def parse_theme(raw: object, context: str) -> dict[str, StyleToken]:
    """Parse the optional mapping-level style_theme key: per-token
    overrides {token: {classes: [...] | str, icon: str|null}}."""
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise _fail(context, "expected a mapping of token overrides")
    theme: dict[str, StyleToken] = {}
    for name, override in raw.items():
        if name not in TOKENS:
            raise _fail(context, f"unknown token {name!r} (known: {sorted(TOKENS)})")
        if not isinstance(override, dict):
            raise _fail(context, f"{name}: expected a mapping with classes/icon")
        _reject_unknown_keys(override, {"classes", "icon"}, f"{context}.{name}")
        classes = override.get("classes")
        if isinstance(classes, list):
            classes = " ".join(str(c) for c in classes)
        if not isinstance(classes, str) or not classes:
            raise _fail(
                context, f"{name}: 'classes' (non-empty list or string) is required",
            )
        icon = override.get("icon", TOKENS[name].icon)
        theme[name] = StyleToken(
            classes, icon if icon is None or isinstance(icon, str) else str(icon),
        )
    return theme
