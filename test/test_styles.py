# test/test_styles.py
import ast
import copy
import json
import re
from pathlib import Path
from typing import Any

import pytest

from dbml_sharepoint.analysis import styles
from dbml_sharepoint.analysis.styles import TOKENS, StyleToken, expand_style, parse_theme


def test_tokens_are_the_documented_severity_set() -> None:
    """Learn column-formatting reference: severity classes with their
    canonical Fluent icon pairings; neutral/muted are background-only
    Fluent classes. No hexes anywhere in the standard."""
    assert TOKENS["good"] == StyleToken("sp-field-severity--good", "CheckMark")
    assert TOKENS["low"] == StyleToken("sp-field-severity--low", "Forward")
    assert TOKENS["warning"] == StyleToken("sp-field-severity--warning", "Error")
    assert TOKENS["severe"] == StyleToken("sp-field-severity--severeWarning", "Warning")
    assert TOKENS["blocked"] == StyleToken("sp-field-severity--blocked", "ErrorBadge")
    assert TOKENS["neutral"].classes == "ms-bgColor-neutralLighter"
    assert TOKENS["neutral"].icon is None
    assert TOKENS["muted"].classes == "ms-bgColor-neutralLight"
    assert "#" not in "".join(t.classes for t in TOKENS.values())


def test_severity_expands_to_the_doc_structure() -> None:
    out = expand_style(
        {"style": "severity", "map": {"Open": "low", "Closed": "good"}},
        "column_formatting.T.Status",
    )
    assert out["elmType"] == "div"
    cls = out["attributes"]["class"]
    assert "@currentField == 'Open'" in cls
    assert "sp-field-severity--low" in cls
    assert "sp-field-severity--good" in cls
    assert "ms-bgColor-neutralLight" in cls          # muted fallback
    assert cls.endswith("+ ' ms-fontColor-neutralSecondary'")
    icon_span, text_span = out["children"]
    assert icon_span["style"] == {"display": "inline-block", "padding": "0 4px"}
    assert "'Forward'" in icon_span["attributes"]["iconName"]
    assert "'CheckMark'" in icon_span["attributes"]["iconName"]
    assert text_span["txtContent"] == "@currentField"
    assert out["style"]["display"] == "=if(@currentField == '', 'none', 'flex')"
    # Cell inset: adjacent same-coloured fills must read as separate cells.
    assert out["style"]["border-radius"] == "4px"
    assert out["style"]["margin"] == "1px 4px 1px 0"


def test_severity_icons_can_be_disabled_and_calculated_matching() -> None:
    out = expand_style(
        {"style": "severity", "calculated": True, "icons": False,
         "map": {"Low": "good", "Extreme": "blocked"}},
        "ctx",
    )
    assert len(out["children"]) == 1                  # no icon span
    cls = out["attributes"]["class"]
    assert "indexOf(@currentField, 'Low') >= 0" in cls
    # calculated-text display cleanup (SP renders 'string;#Value')
    assert ";#" in out["children"][0]["txtContent"]


def test_pill_uses_choice_pill_classes_without_icons() -> None:
    out = expand_style(
        {"style": "pill", "map": {"Open": "low", "Closed": "good"}}, "ctx",
    )
    cls = out["attributes"]["class"]
    assert "sp-css-backgroundColor-BgCornflowerBlue" in cls
    assert "sp-css-backgroundColor-BgMintGreen" in cls
    assert len(out.get("children", [])) == 1          # text span only


def test_data_bar_matches_the_doc_pattern() -> None:
    out = expand_style({"style": "data-bar", "max": 25}, "ctx")
    assert out["attributes"]["class"] == "sp-field-dataBars"
    assert "@currentField >= 25" in out["style"]["width"]
    assert "* 4" in out["style"]["width"]             # 100/25
    assert out["style"]["border-radius"] == "4px"
    assert out["style"]["margin"] == "1px 4px 1px 0"


def test_data_bar_decodes_a_calculated_number() -> None:
    out = expand_style(
        {"style": "data-bar", "max": 25, "calculated": True}, "ctx",
    )
    width = out["style"]["width"]
    assert "Number(substring(@currentField" in width
    assert ";#" in width
    assert out["children"][0]["txtContent"].startswith("=Number(substring(")


def test_data_bar_color_by_takes_severity_tokens_from_another_column() -> None:
    """The mapping-translation pattern: the bar keeps its width semantics
    but wears the severity token mapped from ANOTHER column's value, so a
    score bar carries the same standardised colours as the rating beside
    it. calculated: true switches to the string;# contains-guard."""
    out = expand_style(
        {"style": "data-bar", "max": 25,
         "color_by": {"field": "ResidualRiskRating", "calculated": True,
                      "map": {"Low": "good", "Medium": "warning",
                              "High": "severe", "Extreme": "blocked"}}},
        "ctx",
    )
    cls = out["attributes"]["class"]
    assert "indexOf([$ResidualRiskRating], 'Extreme') >= 0" in cls
    assert "sp-field-severity--blocked" in cls
    assert "sp-field-severity--good" in cls
    assert "ms-fontColor-neutralSecondary" in cls
    assert "ms-bgColor-neutralLight" in cls           # unmapped -> neutral, no false severity
    assert "sp-field-dataBars" not in cls             # native blue fill replaced
    assert "* 4" in out["style"]["width"]             # width semantics unchanged
    assert "@currentField == ''" in out["style"]["display"]


def test_data_bar_color_by_plain_column_uses_equality() -> None:
    out = expand_style(
        {"style": "data-bar", "max": 10,
         "color_by": {"field": "Rating", "map": {"Low": "good"}}},
        "ctx",
    )
    assert "[$Rating] == 'Low'" in out["attributes"]["class"]


def test_calculated_data_bar_keeps_decoding_with_plain_color_source() -> None:
    out = expand_style(
        {"style": "data-bar", "max": 25, "calculated": True,
         "color_by": {"field": "Rating", "map": {"Low": "good"}}},
        "ctx",
    )
    decoded = "Number(substring(@currentField"
    assert decoded in out["style"]["width"]
    assert out["children"][0]["txtContent"].startswith(f"={decoded}")
    assert "[$Rating] == 'Low'" in out["attributes"]["class"]


def test_trend_compares_against_column() -> None:
    out = expand_style({"style": "trend", "against": "Before"}, "ctx")
    icon_span = out["children"][0]
    assert "sp-field-trending--up" in icon_span["attributes"]["class"]
    assert "'SortUp'" in icon_span["attributes"]["iconName"]
    assert "[$Before]" in icon_span["attributes"]["class"]


def test_overdue_date_guard_and_severity_treatment() -> None:
    out = expand_style(
        {"style": "overdue-date",
         "guard": {"field": "Status", "not": ["Closed", "Cancelled"]}},
        "ctx",
    )
    cls = out["attributes"]["class"]
    assert "sp-field-severity--severeWarning" in cls
    assert "[$Status] != 'Closed'" in cls
    assert "[$Status] != 'Cancelled'" in cls
    assert "@currentField < @now" in cls
    assert "'Warning'" in out["children"][0]["attributes"]["iconName"]
    assert out["children"][1]["txtContent"] == "=toLocaleDateString(@currentField)"
    assert out["style"]["border-radius"] == "4px"


def test_overdue_date_decodes_a_calculated_date() -> None:
    out = expand_style(
        {"style": "overdue-date", "calculated": True}, "ctx",
    )
    cls = out["attributes"]["class"]
    assert "Date(substring(@currentField" in cls
    assert ";#" in cls
    assert "toLocaleDateString(Date(substring(" in out["children"][1]["txtContent"]


@pytest.mark.parametrize("spec, fragment", [
    ({"style": "nope"}, "unknown style"),
    ({"style": "severity"}, "requires a non-empty 'map'"),
    ({"style": "severity", "map": {}}, "requires a non-empty 'map'"),
    ({"style": "severity", "map": {"A": "shiny"}}, "unknown token"),
    ({"style": "data-bar"}, "positive integer 'max'"),
    ({"style": "data-bar", "max": 0}, "positive integer 'max'"),
    ({"style": "data-bar", "max": 25, "color_by": {"map": {"A": "good"}}},
     "color_by requires 'field'"),
    ({"style": "data-bar", "max": 25, "color_by": {"field": "R"}},
     "requires a non-empty 'map'"),
    ({"style": "data-bar", "max": 25,
      "color_by": {"field": "R", "map": {"A": "shiny"}}}, "unknown token"),
    ({"style": "trend"}, "requires 'against'"),
    ({"style": "overdue-date", "guard": {"not": ["X"]}}, "guard requires 'field'"),
    # A numeric field emitted `[$42]`, which resolves to no column: SharePoint
    # accepts the formatter and renders nothing.
    ({"style": "overdue-date", "guard": {"field": 42, "not": ["X"]}},
     "guard requires 'field'"),
    ({"style": "overdue-date", "guard": {"field": ""}}, "guard requires 'field'"),
    # A string is iterable, so `not: "Done"` compared against 'D', 'o', 'n', 'e'.
    ({"style": "overdue-date", "guard": {"field": "Status", "not": "Done"}},
     "'not' must be a list"),
    ({"style": "overdue-date", "guard": ["Status"]}, "guard must be a mapping"),
])
def test_invalid_specs_fail_closed_with_context(spec: dict[str, Any], fragment: str) -> None:
    with pytest.raises(ValueError) as err:
        expand_style(spec, "column_formatting.T.C")
    assert "column_formatting.T.C" in str(err.value)
    assert fragment in str(err.value)


def test_theme_overrides_tokens() -> None:
    theme = parse_theme(
        {"good": {"classes": ["my-brand-good"], "icon": "Emoji2"}}, "style_theme",
    )
    out = expand_style(
        {"style": "severity", "map": {"Done": "good"}}, "ctx", theme=theme,
    )
    assert "my-brand-good" in out["attributes"]["class"]
    assert "'Emoji2'" in out["children"][0]["attributes"]["iconName"]


def test_theme_rejects_unknown_tokens() -> None:
    with pytest.raises(ValueError):
        parse_theme({"shiny": {"classes": ["x"]}}, "style_theme")


@pytest.mark.parametrize("spec, typo", [
    ({"style": "severity", "map": {"A": "good"}, "calculatd": True}, "calculatd"),
    ({"style": "severity", "map": {"A": "good"}, "icon": False}, "icon"),
    ({"style": "pill", "map": {"A": "good"}, "calculated": True}, "calculated"),
    ({"style": "data-bar", "max": 25, "colour_by": {}}, "colour_by"),
    ({"style": "data-bar", "max": 25,
      "color_by": {"field": "R", "map": {"A": "good"}, "calculatd": True}}, "calculatd"),
    ({"style": "trend", "aginst": "Target"}, "aginst"),
    ({"style": "overdue-date", "gaurd": {"field": "Status", "not": ["Closed"]}}, "gaurd"),
    ({"style": "overdue-date", "guard": {"field": "Status", "nott": ["Closed"]}}, "nott"),
])
def test_style_spec_unknown_keys_are_rejected(spec: dict[str, Any], typo: str) -> None:
    """A style spec silently ignored everything it did not recognise. A
    typo'd `guard:` renders closed rows as overdue (a red flag on work
    that is finished) and `calculated: true` is documented as required for
    calculated columns while a misspelling of it changed nothing."""
    with pytest.raises(ValueError) as err:
        expand_style(spec, "column_formatting.T.C")
    assert "column_formatting.T.C" in str(err.value)
    assert typo in str(err.value)


def test_theme_override_unknown_keys_are_rejected() -> None:
    with pytest.raises(ValueError, match="icons"):
        parse_theme({"good": {"classes": ["x"], "icons": "Emoji2"}}, "style_theme")


@pytest.mark.parametrize("spec, key", [
    ({"style": "severity", "map": {"A": "good"}, "calculated": "false"}, "calculated"),
    ({"style": "severity", "map": {"A": "good"}, "icons": "false"}, "icons"),
    ({"style": "data-bar", "max": 25,
      "color_by": {"field": "R", "map": {"A": "good"}, "calculated": "false"}},
     "calculated"),
    ({"style": "data-bar", "max": 25, "calculated": "false"}, "calculated"),
    ({"style": "overdue-date", "calculated": "false"}, "calculated"),
])
def test_quoted_booleans_in_style_specs_are_rejected(spec: dict[str, Any], key: str) -> None:
    """`bool("false")` is True, so the cautious spelling meant its
    opposite: `calculated: "false"` switched ON the calculated-value
    handling, and `icons: "false"` kept the icons it was written to
    remove."""
    with pytest.raises(ValueError, match=key):
        expand_style(spec, "column_formatting.T.C")


#: A SharePoint internal name. Anything else inside `[$...]` resolves to no
#: column, which SharePoint accepts and renders as nothing.
_INTERNAL_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_FIELD_REF = re.compile(r"\[\$([^\]]*)\]")


def _field_refs(formatter: dict[str, Any]) -> list[str]:
    """Every column this formatter references, as it appears in the JSON."""
    refs: list[str] = _FIELD_REF.findall(json.dumps(formatter))
    return refs


#: The expander behind each `style:` name, so the accepted keys can be read out
#: of the source instead of restated here and left to rot.
_STYLE_EXPANDERS = {
    "_severity": "severity",
    "_pill": "pill",
    "_data_bar": "data-bar",
    "_trend": "trend",
    "_overdue_date": "overdue-date",
}


def _accepted_keys() -> dict[str, dict[tuple[str, ...], set[str]]]:
    """Every key each style accepts, per nested mapping, read from the
    `_reject_unknown_keys` calls in `analysis/styles.py`.

    Derived rather than listed so a key added to a style cannot escape the
    corpus below by nobody remembering to add it here.
    """
    tree = ast.parse(Path(styles.__file__).read_text(encoding="utf-8"))
    found: dict[str, dict[tuple[str, ...], set[str]]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or node.name not in _STYLE_EXPANDERS:
            continue
        per_path: dict[tuple[str, ...], set[str]] = {}
        for call in ast.walk(node):
            if not isinstance(call, ast.Call):
                continue
            if not isinstance(call.func, ast.Name):
                continue
            if call.func.id != "_reject_unknown_keys":
                continue
            path: tuple[str, ...] = ()
            context_arg = call.args[2]
            if isinstance(context_arg, ast.JoinedStr):
                # f"{context}.color_by" names the nested mapping it guards.
                suffix = "".join(
                    str(part.value)
                    for part in context_arg.values
                    if isinstance(part, ast.Constant)
                )
                path = tuple(suffix.strip(".").split("."))
            per_path[path] = set(ast.literal_eval(call.args[1])) - {"style"}
        found[_STYLE_EXPANDERS[node.name]] = per_path
    return found


#: One legitimate spec per style, the base every hostile substitution mutates.
#: Each carries its style's nested mapping so the nested keys get mutated too.
_LEGITIMATE_SPECS: dict[str, dict[str, Any]] = {
    "severity": {"style": "severity", "map": {"Open": "low", "Closed": "good"}},
    "pill": {"style": "pill", "map": {"Open": "low"}},
    "data-bar": {"style": "data-bar", "max": 25,
                 "color_by": {"field": "Rating", "map": {"Low": "good"}}},
    "trend": {"style": "trend", "against": "Target"},
    "overdue-date": {"style": "overdue-date",
                     "guard": {"field": "Status", "not": ["Closed"]}},
}

#: What a hand-written mapping.yaml plausibly holds where a column name belongs.
_HOSTILE_VALUES: tuple[Any, ...] = (
    42, 0, True, None, "", " ", "Two Words", "Bad]Name", "@currentField",
    ["Closed"], {"field": "Status"},
)


def _hostile_corpus() -> list[tuple[str, dict[str, Any]]]:
    """Each legitimate spec, plus one copy per accepted key per hostile value."""
    accepted = _accepted_keys()
    corpus: list[tuple[str, dict[str, Any]]] = []
    for style_name, base in _LEGITIMATE_SPECS.items():
        corpus.append((style_name, copy.deepcopy(base)))
        for path, keys in accepted[style_name].items():
            for key in sorted(keys):
                for hostile in _HOSTILE_VALUES:
                    spec = copy.deepcopy(base)
                    target: Any = spec
                    for step in path:
                        # KeyError here means the base spec stopped carrying
                        # the nested mapping, so its keys were never mutated.
                        target = target[step]
                    target[key] = hostile
                    corpus.append((style_name, spec))
    return corpus


def test_the_hostile_corpus_covers_every_style_and_key() -> None:
    """The invariant below is only worth its runtime if the corpus is."""
    accepted = _accepted_keys()
    assert set(accepted) == set(styles._STYLES)
    assert set(_LEGITIMATE_SPECS) == set(styles._STYLES)
    # The two styles with a nested mapping guard a second key set inside it.
    assert accepted["data-bar"][("color_by",)] == {"field", "map", "calculated"}
    assert accepted["overdue-date"][("guard",)] == {"field", "not"}
    expected = len(_LEGITIMATE_SPECS) + sum(
        len(keys) * len(_HOSTILE_VALUES)
        for per_path in accepted.values()
        for keys in per_path.values()
    )
    assert len(_hostile_corpus()) == expected > len(_LEGITIMATE_SPECS)


def test_no_style_spec_can_emit_a_malformed_field_reference() -> None:
    """Every `[$...]` a style emits must name a column, whatever produced it.

    `overdue-date` took its guard field on truthiness alone, so `field: 42`
    emitted `[$42]`: a formatter that saves, reads back byte-identical, and
    colours nothing. The oracle needs no knowledge of which key was wrong,
    which is why `trend`'s legitimate `against: 42` passes it. That emits a
    bare numeric literal and never a reference.
    """
    refs_seen = 0
    for style_name, spec in _hostile_corpus():
        try:
            formatter = expand_style(spec, "column_formatting.T.C")
        except ValueError:
            continue
        for ref in _field_refs(formatter):
            refs_seen += 1
            assert _INTERNAL_NAME.match(ref), (
                f"{style_name} accepted {spec!r} and referenced [${ref}]"
            )
    assert refs_seen > 0, "the corpus emitted no field references at all"


def test_trend_still_accepts_a_number_to_compare_against() -> None:
    """The invariant is about references, not types: a numeric `against` is
    documented and emits a bare literal, so it must not be caught by it."""
    out = expand_style({"style": "trend", "against": 42}, "ctx")
    assert "@currentField > 42" in out["children"][0]["attributes"]["class"]
    assert _field_refs(out) == []
