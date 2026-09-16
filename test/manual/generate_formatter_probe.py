"""Generate visual probes from the shipped formatter builders.

Run: uv run python test/manual/generate_formatter_probe.py /tmp/formatter-live-probe
Save a test column's current formatting, then paste each generated JSON into
Format this column / Advanced mode on a disposable test view with one item.
Observe each labelled case, including empty rows, zero labels, colours and
icons. Record discrepancies; the probe does not assert its own observations.
Restore the saved formatting when finished. Constant inputs isolate expression
and rendering behaviour from the column's actual data representation.

2026-09-16: user confirmed numeric-severity, data-bar, dates and text probes
matched their labelled expectations. Trend has automated expression coverage.
"""

import json
import sys
from pathlib import Path
from typing import Any

from dbml_sharepoint.analysis.formatter_values import quoted
from dbml_sharepoint.analysis.styles import expand_style
from dbml_sharepoint.bundle import write_artifact


def substitute(value: Any, literal: str) -> Any:
    if isinstance(value, dict):
        return {key: substitute(child, literal) for key, child in value.items()}
    if isinstance(value, list):
        return [substitute(child, literal) for child in value]
    if isinstance(value, str):
        return value.replace("@currentField", literal).replace(
            "@now", "Date('2026-09-16T12:00:00Z')",
        )
    return value


def probe(spec: dict[str, Any], cases: list[tuple[Any, str]]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for value, expected in cases:
        literal = quoted(value) if isinstance(value, str) else str(value)
        cell = substitute(expand_style(spec, "probe"), literal)
        rows.append({
            "elmType": "div", "style": {"padding": "6px", "width": "300px"},
            "children": [
                {"elmType": "div", "txtContent": f"{value!r}: expected {expected}"},
                cell,
            ],
        })
    return {"$schema": "https://developer.microsoft.com/json-schemas/sp/v2/column-formatting.schema.json",
            "elmType": "div", "debugMode": True, "children": rows}


def generate(destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    specs: dict[str, tuple[dict[str, Any], list[tuple[Any, str]]]] = {
        "numeric-severity": (
            {"style": "numeric-severity", "calculated": True,
             "bands": [{"max": 0, "token": "good"}, {"max": 1, "token": "warning"}],
             "otherwise": "severe"},
            [(0, "green check and 0"), ("float;#0", "green check and 0"),
             (1, "amber error icon and 1"), (2, "severe warning and 2"),
             ("bad", "neutral, no icon, bad"), ("", "no formatted cell"),
             ("float;#", "no formatted cell")],
        ),
        "data-bar": (
            {"style": "data-bar", "max": 25, "calculated": True},
            [(-1, "zero-width bar, visible -1"), (0, "zero-width bar, visible 0"),
             ("float;#12.5", "half-width bar, 12.5"), (25, "full bar, 25"),
             (30, "full bar, 30"), ("bad", "neutral, bad"), ("", "no formatted cell")],
        ),
        "trend": (
            {"style": "trend", "against": 1, "calculated": True},
            [(0, "down arrow and 0"), (1, "no arrow and 1"),
             ("float;#2", "up arrow and 2"), ("bad", "no arrow, bad"),
             ("", "no formatted cell")],
        ),
        "dates": (
            {"style": "overdue-date", "calculated": True},
            [("2026-09-15T00:00:00Z", "overdue warning and locale date"),
             ("datetime;#2026-09-15T00:00:00Z", "same as the preceding plain date"),
             ("2026-09-17T00:00:00Z", "date without warning"),
             ("bad", "neutral, bad"), ("", "no formatted cell"),
             ("datetime;#", "no formatted cell")],
        ),
        "text": (
            {"style": "severity", "calculated": True,
             "map": {"Approved": "good", "Not Approved": "blocked"}},
            [("Approved", "green check"), ("string;#Approved", "green check"),
             ("Not Approved", "blocked"), ("string;#Not Approved", "blocked"),
             ("Approved later", "neutral"), ("", "no formatted cell")],
        ),
    }
    for name, (spec, cases) in specs.items():
        write_artifact(
            destination / f"{name}.json", json.dumps(probe(spec, cases), indent=2) + "\n",
        )


if __name__ == "__main__":
    generate(Path(sys.argv[1]))
