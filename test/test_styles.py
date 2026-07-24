# test/test_styles.py
from typing import Any

import pytest

from dbml_sharepoint.styles import TOKENS, StyleToken, expand_style, parse_theme


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
