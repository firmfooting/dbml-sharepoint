from pathlib import Path
from typing import Any

import pytest
from _builders import ID_PK, TITLE, table
from _packs import pack
from _paths import SOLUTION_TEMPLATES

from dbml_sharepoint.analysis.reporting.plan import build_plans
from dbml_sharepoint.catalogue import load_solution
from dbml_sharepoint.generators.assessgen import assess_targets
from dbml_sharepoint.generators.demogen import generate_demo_js
from dbml_sharepoint.generators.jsgen import build_schema_json
from dbml_sharepoint.generators.manifestgen import generate_manifest
from dbml_sharepoint.generators.rollbackgen import generate_rollback_js
from dbml_sharepoint.model.errors import MappingValueError
from dbml_sharepoint.model.mapping_loader import load_mapping
from dbml_sharepoint.model.parser import parse_dbml
from dbml_sharepoint.model.release import load_release
from dbml_sharepoint.wizard import TemplateChoice, _read_facts


def test_legal_library_identity_and_navigation_are_consistent() -> None:
    root = SOLUTION_TEMPLATES / "legal-compliance-register"
    schema = parse_dbml(root / "10-design/schema.dbml")
    bundle = load_mapping(root / "20-configure/mapping.yaml")
    release = load_release(root / "20-configure/release.yaml")
    built = build_schema_json(schema, bundle, "default")
    title = "Legislative Compliance"
    assert built["lists"][0]["title"] == title
    assert built["lists"][0]["internal_name"] == "LegislativeCompliance"
    committee = next(
        f for f in built["lists"][0]["fields_phase1"] if f["title"] == "OversightCommittee"
    )
    assert committee["display_title"] == "Oversight Committee"
    assert not committee["body"].get("Required", False)
    assert committee["body"]["FieldTypeKind"] == 6
    assert committee["body"]["Choices"]["results"] == [
        "Audit and Risk Committee", "Clinical Governance Committee", "Executive Committee",
    ]
    assert list(dict(assess_targets(schema, bundle, "default")["list_markers"])) == [title]
    assert all(v["list"] == title and v["view_fields"][0] == "DocIcon" for v in built["views"])
    folder = next(v for v in built["views"] if v["title"] == "Folder View")
    assert folder["scope"] == 0
    assert "<Where>" not in folder["caml_query"]
    assert next(v for v in built["views"] if v["title"] == "Pending")["set_default"]
    plan, = build_plans(schema, bundle, "default")
    assert plan.list_title == title
    assert plan.item_url_path == "/LegislativeCompliance/Forms/DispForm.aspx?ID="
    args: dict[str, Any] = dict(
        release=release, site_url="https://example.sharepoint.com/sites/test",
        site_role="default", source_dbml="schema.dbml", generated_at="2026-09-15T00:00:00Z",
    )
    for generator in (generate_demo_js, generate_rollback_js):
        emitted = generator(schema=schema, bundle=bundle, **args)
        assert title in emitted
        assert "LC_Document" not in emitted
    manifest = generate_manifest(
        schema_json=built, findings=[], bundle=bundle,
        source_mtime="2026-09-15T00:00:00Z", **args,
    )
    assert "Immutable library URL name: `LegislativeCompliance`" in manifest
    assert "filter:" in manifest
    assert "sort: Modified desc" in manifest
    solution = load_solution("legal-compliance-register")
    facts = _read_facts(solution)
    assert TemplateChoice(
        solution, "TEST_", facts.entity_roles, facts.entity_titles,
    ).list_titles("default") == (title,)


@pytest.mark.parametrize("spec", [
    "internal_name: ../escape", "internal_name: 'bad name'", "internal_name: 123",
    "title: '../escape'", "title: '   '",
])
def test_library_identity_rejects_invalid_names(tmp_path: Path, spec: str) -> None:
    with pytest.raises(ValueError):
        pack(tmp_path, dbml=table("Doc", ID_PK, TITLE), mapping=f"""
            entities:
              Doc:
                kind: DocumentLibrary
                base_template: 101
                site_role: default
                {spec}
        """)


def test_two_entities_cannot_claim_the_same_title(tmp_path: Path) -> None:
    with pytest.raises(MappingValueError, match="duplicate deployed title"):
        pack(tmp_path, dbml=table("A", ID_PK, TITLE) + table("B", ID_PK, TITLE), mapping="""
            entities:
              A: {kind: List, base_template: 100, site_role: default, title: Same}
              B: {kind: List, base_template: 100, site_role: default, title: same}
        """)


@pytest.mark.parametrize("length", [255, 256])
def test_explicit_title_length_boundary(tmp_path: Path, length: int) -> None:
    mapping = f"""
        entities:
          Doc:
            kind: DocumentLibrary
            base_template: 101
            site_role: default
            title: {'A' * length}
    """
    if length == 256:
        with pytest.raises(MappingValueError, match="at most 255"):
            pack(tmp_path, dbml=table("Doc", ID_PK, TITLE), mapping=mapping)
    else:
        pack(tmp_path, dbml=table("Doc", ID_PK, TITLE), mapping=mapping)


def test_rename_cannot_declare_an_immutable_root(tmp_path: Path) -> None:
    with pytest.raises(MappingValueError, match="internal_name cannot be combined"):
        pack(tmp_path, dbml=table("Doc", ID_PK, TITLE), mapping="""
            entities:
              Doc:
                kind: DocumentLibrary
                base_template: 101
                site_role: default
                internal_name: NewRoot
                renamed_from: [OldDoc]
        """)
