"""The Involvement deployment and reporting contract."""

import json
from pathlib import Path
from typing import Any

import pytest
from _paths import SOLUTION_TEMPLATES

from dbml_sharepoint.analysis.resolve import resolve
from dbml_sharepoint.generators.jsgen import build_schema_json
from dbml_sharepoint.model.mapping_loader import load_mapping
from dbml_sharepoint.model.parser import parse_dbml
from dbml_sharepoint.pipeline import execute_build

ROOT = SOLUTION_TEMPLATES / "programme-governance"


@pytest.fixture(scope="module")
def declaration() -> dict[str, Any]:
    schema = parse_dbml(ROOT / "10-design/schema.dbml")
    bundle = load_mapping(ROOT / "20-configure/mapping.yaml")
    return build_schema_json(
        schema, bundle, "default", resolved=resolve(schema, bundle.mapping),
    )


def test_involvement_fields_preserve_the_upgrade_contract(declaration: dict[str, Any]) -> None:
    involvement = next(x for x in declaration["lists"] if x["title"] == "GOV_Involvement")
    fields = {f["title"]: f for f in involvement["fields_phase1"]}
    assert "NextContact" not in fields
    for name in ("Lead", "ContactDate", "EngagementPlan", "Notes"):
        assert not fields[name]["body"].get("Required", False)
    assert fields["Lead"]["body"]["FieldTypeKind"] == 20
    assert fields["Lead"]["body"]["SelectionMode"] == 0
    assert not fields["Lead"]["body"].get("AllowMultipleValues", False)
    for name in ("EngagementPlan", "Notes"):
        assert fields[name]["body"]["FieldTypeKind"] == 3
        assert fields[name]["body"]["RichText"] is False
        assert fields[name]["body"]["AppendOnly"] is False
    assert fields["ContactDate"]["display_title"] == "Contact Date"
    assert fields["ContactDate"]["body"]["DisplayFormat"] == 0
    assert {"list": "GOV_Involvement", "field": "ContactDate"} in declaration["indexed_columns"]
    assert fields["EngagementStatus"]["body"]["Choices"]["results"] == ["Identified", "Engaged"]
    assert fields["EngagementStatus"]["body"]["DefaultValue"] == "Identified"
    assert fields["Channel"]["body"]["Choices"]["results"] == [
        "Governance forum", "Meeting", "Email", "Report or dashboard",
    ]
    assert fields["Channel"]["body"]["DefaultValue"] == "Email"
    formatter = json.loads(fields["ContactDate"]["custom_formatter"])
    assert "[$EngagementStatus] != 'Engaged'" in formatter["attributes"]["class"]
    assert "[$EngagementStatus] != ''" in formatter["attributes"]["class"]


def test_involvement_form_and_views_use_the_new_fields(declaration: dict[str, Any]) -> None:
    form = next(x for x in declaration["form_formatting"] if x["list"] == "GOV_Involvement")
    sections = json.loads(form["client_form_custom_formatter"])["bodyJSONFormatter"]["sections"]
    assert sections[0]["fields"] == ["Input", "Activity", "Stakeholder"]
    assert sections[1]["fields"] == [
        "Involvement", "Lead", "Engagement Plan", "Channel", "Contact Date",
        "Engagement Status", "Notes",
    ]
    views = {v["title"]: v for v in declaration["views"] if v["list"] == "GOV_Involvement"}
    for name in (
        "By activity", "By stakeholder", "Identified, not yet engaged", "Consultation load",
    ):
        assert "Lead" in views[name]["view_fields"]
    for view in views.values():
        assert "NextContact" not in view["view_fields"]
        assert "NextContact" not in view["caml_query"]
    backlog = views["Identified, not yet engaged"]["caml_query"]
    assert "Identified" in backlog
    assert "Scheduled" not in backlog
    assert 'Name="ContactDate"' in backlog


@pytest.mark.parametrize("seed", [False, True])
def test_involvement_builds_with_current_reporting_and_demo_data(
    tmp_path: Path, seed: bool,
) -> None:
    execute_build(
        schema=ROOT / "10-design/schema.dbml",
        mapping=ROOT / "20-configure/mapping.yaml",
        release=ROOT / "20-configure/release.yaml",
        site_url="https://example.sharepoint.com/sites/ci",
        site_role="default", time_zone="UTC", out=tmp_path, seed=seed,
    )
    reporting = "\n".join(
        p.read_text(encoding="utf-8") for p in (tmp_path / "reporting").rglob("*") if p.is_file()
    )
    assert "HasContactDate" in reporting
    assert "NextContact" not in reporting
    assert '"Scheduled"' not in reporting
    deploy = (tmp_path / "deploy.js.txt").read_text(encoding="utf-8")
    assert '"NextContact"' not in deploy
    assert '"EngagementPlan"' in deploy
