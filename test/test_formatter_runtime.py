"""Exercise emitted expressions with documented operators, not a mock SharePoint UI."""

import json
import re
from typing import Any

import pytest
from _node import NODE, run_node

from dbml_sharepoint.analysis.styles import expand_style
from dbml_sharepoint.extract.inverse import invert_column_formatting

pytestmark = pytest.mark.skipif(NODE is None, reason="node is required")


def render(
    spec: dict[str, Any], value: Any, fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    formatter = expand_style(spec, "test")

    def compile_value(item: Any) -> str:
        if isinstance(item, dict):
            return "{" + ",".join(json.dumps(k) + ":" + compile_value(v)
                                  for k, v in item.items()) + "}"
        if isinstance(item, list):
            return "[" + ",".join(map(compile_value, item)) + "]"
        if not isinstance(item, str) or not item.startswith("="):
            return "value" if item == "@currentField" else json.dumps(item)
        parts = re.split(r"('(?:[^']|'')*')", item[1:])
        for i, part in enumerate(parts):
            if i % 2:
                parts[i] = json.dumps(part[1:-1].replace("''", "'"))
            else:
                part = part.replace("@currentField", "value").replace("@now", "now")
                part = re.sub(r"\[\$([^\]]+)\]", lambda m: "fields[" + json.dumps(m[1]) + "]", part)
                part = re.sub(r"\bif\(", "choose(", part)
                parts[i] = re.sub(r"\bDate\(", "asDate(", part)
        return "(" + "".join(parts) + ")"

    script = """
const toString = String;
const indexOf = (text, needle) => text.indexOf(needle);
const substring = (text, start, end) => text.substring(start, end);
const choose = (condition, yes, no) => condition ? yes : no;
const asDate = value => new Date(value);
const toLocaleDateString = date =>
    isNaN(Number(date)) ? 'Invalid Date' : date.toISOString().slice(0, 10);
const now = new Date('2026-09-16T12:00:00Z');
"""
    result = run_node(script + f"const value = {json.dumps(value)};\n"
                      + f"const fields = {json.dumps(fields or {})};\n"
                      + "console.log(JSON.stringify(" + compile_value(formatter) + "));\n")
    rendered: dict[str, Any] = json.loads(result)
    return rendered


BANDS = {"style": "numeric-severity", "calculated": True,
         "bands": [{"max": 0, "token": "good"}, {"max": 1, "token": "warning"}],
         "otherwise": "severe"}


@pytest.mark.parametrize("value, treatment", [
    (-1, "good"), (0, "good"), (0.5, "warning"), (1, "warning"), (2, "severeWarning"),
    ("float;#0", "good"), ("float;#1", "warning"), ("float;#2", "severeWarning"),
    ("bad", "muted"), ("NaN", "muted"), ("Infinity", "muted"),
])
def test_numeric_bands(value: Any, treatment: str) -> None:
    cell = render(BANDS, value)
    expected = ("ms-bgColor-neutralLight" if treatment == "muted"
                else f"sp-field-severity--{treatment}")
    assert expected in cell["attributes"]["class"]
    assert cell["style"]["display"] == "flex"
    if treatment == "muted":
        assert cell["children"][0]["attributes"]["iconName"] == ""
        assert cell["children"][1]["txtContent"] == value


@pytest.mark.parametrize("value", ["", "float;#"])
def test_numeric_bands_hide_empty_values(value: str) -> None:
    assert render(BANDS, value)["style"]["display"] == "none"


@pytest.mark.parametrize("calculated", [False, True])
@pytest.mark.parametrize("value, width", [(-1, "0%"), (0, "0%"), (1, "4%"),
                                          (12.5, "50%"), (25, "100%"), (30, "100%")])
def test_bar_bounds_preserve_the_label(calculated: bool, value: float, width: str) -> None:
    cell = render({"style": "data-bar", "max": 25, "calculated": calculated},
                  f"float;#{value}" if calculated else value)
    assert cell["style"]["width"] == width
    assert cell["children"][0]["txtContent"] == value
    assert cell["style"]["display"] == "flex"


def test_invalid_bar_is_neutral_and_keeps_the_input() -> None:
    cell = render({"style": "data-bar", "max": 25}, "bad")
    assert cell["attributes"]["class"] == "ms-bgColor-neutralLight"
    assert cell["children"][0]["txtContent"] == "bad"


@pytest.mark.parametrize("value", ["Not Approved", "string;#Not Approved", "Approved later"])
def test_calculated_text_matches_exactly(value: str) -> None:
    cell = render({"style": "severity", "calculated": True,
                   "map": {"Approved": "good", "Not Approved": "blocked"}}, value)
    assert "sp-field-severity--good" not in cell["attributes"]["class"]


def test_calculated_colour_source_matches_exactly() -> None:
    spec = {"style": "data-bar", "max": 25, "color_by": {
        "field": "Rating", "calculated": True, "map": {"High": "severe"},
    }}
    cell = render(spec, 25, {"Rating": "string;#Not High"})
    assert "severeWarning" not in cell["attributes"]["class"]
    assert "severeWarning" in render(spec, 25, {"Rating": "string;#High"})["attributes"]["class"]


@pytest.mark.parametrize("current, baseline, icon", [
    (0, 0, ""), (1, 0, "SortUp"), (0, 1, "SortDown"), ("bad", 1, ""), (1, "bad", ""),
    (1, "", ""), ("float;#2", "float;#1", "SortUp"),
])
def test_trend_operands(current: Any, baseline: Any, icon: str) -> None:
    cell = render({"style": "trend", "against": "Baseline", "calculated": True,
                   "against_calculated": True}, current, {"Baseline": baseline})
    assert cell["children"][0]["attributes"]["iconName"] == icon
    if not icon:
        assert cell["children"][0]["attributes"]["class"] == ""


@pytest.mark.parametrize("value, display, icon", [
    ("", "none", ""), ("datetime;#", "none", ""), ("bad", "flex", ""),
    ("2026-09-15T00:00:00Z", "flex", "Warning"),
    ("datetime;#2026-09-15T00:00:00Z", "flex", "Warning"),
    ("2026-09-17T00:00:00Z", "flex", ""),
])
def test_date_boundaries(value: str, display: str, icon: str) -> None:
    cell = render({"style": "overdue-date", "calculated": True}, value)
    assert cell["style"]["display"] == display
    assert cell["children"][0]["attributes"]["iconName"] == icon
    if value == "bad":
        assert cell["children"][1]["txtContent"] == "bad"
        assert cell["attributes"]["class"] == "ms-bgColor-neutralLight"


@pytest.mark.parametrize("spec", [
    BANDS, {**BANDS, "icons": False},
    {"style": "numeric-severity", "bands": [{"max": -1.5, "token": "good"}],
     "otherwise": "blocked"},
    {"style": "severity", "map": {"O'Brien": "good"}, "calculated": True},
    {"style": "severity", "map": {"Open": "low"}},
    {"style": "overdue-date", "calculated": True},
    {"style": "overdue-date", "guard": {"field": "Status", "not": ["Done"]}},
])
def test_current_styles_round_trip(spec: dict[str, Any]) -> None:
    formatter = expand_style(spec, "test")
    recovered, _ = invert_column_formatting(json.dumps(formatter), "test")
    assert recovered is not None
    assert expand_style(recovered, "test") == formatter


@pytest.mark.parametrize("changes", [
    {"bands": []}, {"bands": [1]}, {"bands": [{"max": True, "token": "good"}]},
    {"bands": [{"max": float("inf"), "token": "good"}]},
    {"bands": [{"max": float("nan"), "token": "good"}]},
    {"bands": [{"max": 1, "token": "good"}, {"max": 1, "token": "severe"}]},
    {"bands": [{"max": 1, "token": "good"}, {"max": 0, "token": "severe"}]},
    {"bands": [{"max": 1, "token": "unknown"}]},
    {"bands": [{"max": 1, "token": True}]}, {"otherwise": None},
    {"bands": [{"max": 1, "token": "good", "typo": 1}]},
])
def test_invalid_bands_fail_closed(changes: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        expand_style({**BANDS, **changes}, "test")


@pytest.mark.parametrize("attributes", [None, [], 1, {"class": 1}])
def test_unrecognised_formatter_shapes_are_preserved(attributes: Any) -> None:
    raw = {"elmType": "div", "attributes": attributes}
    assert invert_column_formatting(json.dumps(raw), "test") == (None, raw)


@pytest.mark.parametrize("value", [float("inf"), float("nan"), 10**400])
def test_nonfinite_numeric_configuration_is_refused(value: Any) -> None:
    for spec in ({"style": "trend", "against": value},
                 {**BANDS, "bands": [{"max": value, "token": "good"}]},
                 {"style": "data-bar", "max": value}):
        with pytest.raises(ValueError):
            expand_style(spec, "test")


def test_visual_probe_generation(tmp_path: Any) -> None:
    import runpy

    from _paths import MANUAL

    generate = runpy.run_path(str(MANUAL / "generate_formatter_probe.py"))["generate"]
    generate(tmp_path)
    assert {p.stem for p in tmp_path.glob("*.json")} == {
        "numeric-severity", "data-bar", "dates", "text", "trend",
    }
    for path in tmp_path.glob("*.json"):
        raw = path.read_text(encoding="utf-8")
        assert "@currentField" not in raw and "@now" not in raw and "[$" not in raw
        assert json.loads(raw)["debugMode"] is True
