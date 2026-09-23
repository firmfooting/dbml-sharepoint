"""Programme delivery views preserve completion and overdue-date workflows."""

import json
from typing import Any

import pytest
from _node import NODE, run_node
from _paths import SOLUTION_TEMPLATES

from dbml_sharepoint.analysis.resolve import resolve
from dbml_sharepoint.generators.jsgen import build_schema_json
from dbml_sharepoint.model.mapping_loader import load_mapping
from dbml_sharepoint.model.parser import parse_dbml

ROOT = SOLUTION_TEMPLATES / "programme-governance"


@pytest.fixture(scope="module")
def declaration() -> dict[str, Any]:
    schema = parse_dbml(ROOT / "10-design/schema.dbml")
    bundle = load_mapping(ROOT / "20-configure/mapping.yaml")
    return build_schema_json(
        schema, bundle, "default", resolved=resolve(schema, bundle.mapping),
    )


@pytest.mark.parametrize("title", [
    "My overdue", "Open by risk", "Open by issue", "Open by decision",
])
def test_action_views_can_record_completion(declaration: dict[str, Any], title: str) -> None:
    view = next(v for v in declaration["views"]
                if v["list"] == "GOV_Action" and v["title"] == title)
    assert "Status" in view["view_fields"]
    assert "CompletedDate" in view["view_fields"]


@pytest.mark.skipif(NODE is None, reason="node is required")
@pytest.mark.parametrize("due, overdue", [
    ("new Date(2026, 8, 20)", True),
    ("new Date(2026, 8, 21)", False),
    ("new Date(2026, 8, 21, 23, 59)", False),
    ("new Date(2026, 8, 22)", False),
    ("''", False),
])
def test_action_row_wash_excludes_today_and_empty_dates(
    declaration: dict[str, Any], due: str, overdue: bool,
) -> None:
    view = next(v for v in declaration["views"]
                if v["list"] == "GOV_Action" and v["title"] == "My actions")
    formatter = json.loads(view["formatting"])
    expression = formatter["additionalRowClass"][1:]
    expression = expression.replace("@now", "now").replace("[$DueDate]", "due")
    expression = expression.replace("if(", "choose(")
    result = run_node(
        "const now = new Date(2026, 8, 21, 12);\n"
        "const choose = (condition, yes, no) => condition ? yes : no;\n"
        "const toDateString = value => value === '' ? '' : value.toDateString();\n"
        f"const due = {due};\n"
        f"console.log(JSON.stringify({expression}));\n"
    )
    assert bool(json.loads(result)) is overdue
