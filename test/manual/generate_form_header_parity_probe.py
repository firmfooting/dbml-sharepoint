"""Generate form-header-parity-probe.js: a generated form header against its calculated columns.

Run: uv run python test/manual/generate_form_header_parity_probe.py OUTPUT.js [ZONE]
The header is built by the same code a blueprint build runs, for the site zone named (default
Australia/Melbourne), so the zone in the probe's site-zone fixture row is the one the header was
generated for. A test pins the committed probe to this generator's output.
"""

import hashlib
import json
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dbml_sharepoint.analysis.form_header import resolve_form_headers
from dbml_sharepoint.analysis.formatter_values import quoted
from dbml_sharepoint.analysis.styles import TOKENS
from dbml_sharepoint.bundle import write_artifact
from dbml_sharepoint.model.mapping_loader import load_mapping
from dbml_sharepoint.model.parser import parse_dbml

DEFAULT_ZONE = "Australia/Melbourne"
DATE_ORDER = "dmy"
LIST_TITLE = "FormHeaderParity"
OWNERSHIP = "dbml-sharepoint form-header-parity probe scratch list. Safe to delete."
APOSTROPHE = "Can't start"
# The badge text in form.yaml; the header's span is then given a hand-written expression literal.
APOSTROPHE_SLOT = "Apostrophe slot"
DAYS = {"Low": 14, "Medium": 21, "High": 30, "Critical": 28}
RANK = 'IF([Impact]="Low",1,IF([Impact]="Medium",2,IF([Impact]="High",3,4)))'
RISK_RANK = 'IF([Risk]="Low",1,IF([Risk]="Medium",2,3))'
# Each column: name, result kind, formula. Wait comes first because Chased reads it.
FORMULAS = {
    "Wait": 'IF([Impact]="Critical",28,IF([Impact]="High",30,14))',
    "Cutoff": f'IF(ISBLANK([Start]),"",[Start]+CHOOSE({RANK},14,21,30,28))',
    "Review": (
        'IF(ISBLANK([Start]),"",DATE(YEAR([Start]),MONTH([Start])'
        f"+CHOOSE({RISK_RANK},3,6,12),DAY([Start])))"
    ),
    "Chased": 'IF(ISBLANK([Start]),"",[Start]+[Wait])',
    "Rating": (
        f'CHOOSE({RANK},CHOOSE({RISK_RANK},"Low","Low","Medium"),'
        f'CHOOSE({RISK_RANK},"Low","Medium","High"),CHOOSE({RISK_RANK},"Medium","High","High"),"High")'
    ),
}
KINDS = {"Wait": "number", "Cutoff": "date", "Review": "date", "Chased": "date", "Rating": "text"}
# Each bubble label differs from its column name, so the form body never reads as the header.
BUBBLES = [
    {"column": "Cutoff", "label": "Due by", "kind": "date"},
    {"column": "Review", "label": "Review on", "kind": "date"},
    {"column": "Chased", "label": "Chased on", "kind": "date"},
    {"column": "Rating", "label": "Rating now", "kind": "text"},
]
CHOICES = {
    "Status": ["Open", "Done"],
    "Impact": ["Low", "Medium", "High", "Critical"],
    "Risk": ["Low", "Medium", "High"],
}
UNLISTED = "Unlisted value"
# Month ends, year ends, 28 and 29 February, and the days around 2026 daylight changes.
START_DATES = [
    "2025-12-31", "2026-01-01", "2026-01-31", "2026-02-28", "2026-03-01", "2024-02-28",
    "2024-02-29", "2024-03-01", "2026-04-04", "2026-04-05", "2026-10-03", "2026-10-04",
]
MONTH_END = "2026-01-31"

SCHEMA = """Project parity { database_type: 'SharePoint Online' }
Enum task_status {
  "Open"
  "Done"
}
Enum impact {
  "Low"
  "Medium"
  "High"
  "Critical"
}
Enum risk {
  "Low"
  "Medium"
  "High"
}
Table Task {
  Id      int       [pk, increment]
  Title   nvarchar  [not null]
  Status  task_status
  Impact  impact
  Risk    risk
  Start   date
  Cutoff  calculated_date
  Review  calculated_date
  Chased  calculated_date
  Rating  calculated_text
  Wait    calculated_number
}
"""

FORM = f"""Task:
  header:
    title: {{ column: Title, blank: "Untitled" }}
    subtitle:
      - Status
      - {{ text: "Impact {{Impact}}", columns: [Impact] }}
    rows:
      - items:
          - {{ column: Cutoff, label: "Due by", date_order: {DATE_ORDER}, due: true }}
          - {{ column: Review, label: "Review on", date_order: {DATE_ORDER} }}
          - {{ column: Chased, label: "Chased on", date_order: {DATE_ORDER} }}
          - {{ column: Rating, label: "Rating now", tokens: {{ High: severe, Medium: warning, Low: good }} }}
          - badge: {{ text: "{APOSTROPHE_SLOT}", token: warning, when: {{ field: Status, op: eq, value: Open }} }}
"""  # noqa: E501 -- a form.yaml flow line


def _mapping() -> str:
    formulas = "\n".join(f"    {name}: {json.dumps('=' + f)}" for name, f in FORMULAS.items())
    return f"""prefix: "APP_"
prefix_owner: "Test"
entities:
  Task: {{ kind: List, base_template: 100, site_role: default }}
cross_site_reference_columns: []
versioning:
  default: {{ enable_versioning: true, major_version_limit: 500, enable_minor_versions: false }}
  overrides: {{}}
enum_sources: {{}}
watched_lists: []
calculated_formulas:
  Task:
{formulas}
"""


def _fill_slot(node: object) -> int:
    """Replace the slot text with an expression literal holding the apostrophe; the count."""
    found = 0
    if isinstance(node, dict):
        if node.get("txtContent") == APOSTROPHE_SLOT:
            node["txtContent"] = "=" + quoted(APOSTROPHE)
            found += 1
        found += sum(_fill_slot(v) for v in node.values())
    elif isinstance(node, list):
        found += sum(_fill_slot(v) for v in node)
    return found


def _header(zone: str) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        sources = (("schema.dbml", SCHEMA), ("mapping.yaml", _mapping()), ("form.yaml", FORM))
        for name, text in sources:
            write_artifact(root / name, text)
        bundle = load_mapping(root / "mapping.yaml")
        resolved, findings = resolve_form_headers(parse_dbml(root / "schema.dbml"), bundle, zone)
    assert not findings, findings
    header = resolved.mapping.form_formatting["Task"].header
    assert header is not None
    # A platform observation, not core output: the build refuses this literal.
    assert _fill_slot(header) == 1
    return json.dumps({"headerJSONFormatter": header}, separators=(",", ":"))


def _zone_biases(zone: str) -> dict[str, int]:
    """SharePoint's regional time zone fields: minutes west of UTC, then the daylight offset."""
    tz = ZoneInfo(zone)
    offsets: list[int] = []
    for month in (1, 7):
        offset = datetime(2026, month, 1, tzinfo=UTC).astimezone(tz).utcoffset()
        assert offset is not None
        offsets.append(int(offset.total_seconds() // 60))
    standard, daylight = min(offsets), max(offsets)
    return {"Bias": -standard, "StandardBias": 0, "DaylightBias": -(daylight - standard)}


def _items() -> list[dict[str, object]]:
    grid: list[tuple[str | None, str | None, str | None, str]] = []
    for start in START_DATES:
        grid.append((start, "High", "Medium", "Done" if len(grid) % 2 else "Open"))
    grid.append((None, "Low", "Low", "Open"))
    for impact in CHOICES["Impact"]:
        for risk in CHOICES["Risk"]:
            grid.append((MONTH_END, impact, risk, "Open" if len(grid) % 2 else "Done"))
    grid += [
        (MONTH_END, None, "High", "Open"), (MONTH_END, "Low", None, "Open"),
        (MONTH_END, UNLISTED, "Low", "Open"), (MONTH_END, "Low", UNLISTED, "Done"),
    ]
    items: list[dict[str, object]] = [
        {"title": f"Case {n:02d}", "Start": s, "Impact": i, "Risk": r, "Status": st}
        for n, (s, i, r, st) in enumerate(grid, 1)
    ]
    # Start is set at run time from the site's own day, so the due day and its neighbours are real.
    for n, offset in enumerate((-1, 0, 1), len(items) + 1):
        items.append({
            "title": f"Case {n:02d}", "Start": None, "Impact": "Low", "Risk": "Low",
            "Status": "Open", "dueOffset": offset,
        })
    return items


def _data(zone: str) -> dict[str, object]:
    columns: list[dict[str, object]] = [
        {"name": name, "kind": "choice", "choices": choices} for name, choices in CHOICES.items()
    ]
    columns.append({"name": "Start", "kind": "date"})
    for name, formula in FORMULAS.items():
        columns.append(
            {"name": name, "kind": "calc", "result": KINDS[name], "formula": "=" + formula},
        )
    return {
        "list": LIST_TITLE, "ownership": OWNERSHIP, "dateOrder": DATE_ORDER,
        "zone": _zone_biases(zone), "formatter": _header(zone), "columns": columns,
        "items": _items(), "bubbles": BUBBLES, "days": DAYS, "monthEnd": MONTH_END,
        "blockedClass": TOKENS["blocked"].classes, "apostrophe": APOSTROPHE,
        "dueLabel": "Due by", "markerLabel": "Rating now",
    }


def render(zone: str = DEFAULT_ZONE) -> str:
    """The probe text for a site zone, stamped with the digest of its own text."""
    text = TEMPLATE.replace("__DATA__", json.dumps(_data(zone), indent=2))
    stamp = hashlib.sha256(text.encode()).hexdigest()[:8]
    return text.replace("00000000", stamp)


TEMPLATE = (Path(__file__).parent / "templates" / "form-header-parity-probe.js.in").read_text(
    encoding="utf-8",
)


if __name__ == "__main__":
    write_artifact(Path(sys.argv[1]), render(sys.argv[2] if len(sys.argv) > 2 else DEFAULT_ZONE))
