# test/test_assessgen.py
from pathlib import Path

from dbml_sharepoint.assessgen import (
    assess_targets,
    derive_requirements,
)
from dbml_sharepoint.mapping_loader import MappingBundle, load_mapping
from dbml_sharepoint.parser import Schema, parse_dbml

FIXTURES = Path(__file__).parent / "fixtures"


def _simple() -> tuple[Schema, MappingBundle]:
    return (
        parse_dbml(FIXTURES / "simple.dbml"),
        load_mapping(FIXTURES / "sharepoint-mapping.yaml"),
    )


def test_always_requirements_present() -> None:
    schema, bundle = _simple()
    keys = {r.key for r in derive_requirements(schema, bundle, "default")}
    assert {"manage_lists_bit", "site_not_locked"} <= keys
    assert "collision:APP_Project" in keys
    assert "collision:APP_Task" in keys


def test_base_template_requirements_from_entities() -> None:
    schema, bundle = _simple()
    keys = {r.key for r in derive_requirements(schema, bundle, "default")}
    assert "list_template_100" in keys


def test_conditional_requirements_absent_on_bare_mapping(tmp_path: Path) -> None:
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Risk {\n  Id int [pk, increment]\n  Title nvarchar [not null]\n}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Risk: { kind: List, base_template: 100, site_role: default }\n",
        encoding="utf-8",
    )
    schema = parse_dbml(tmp_path / "s.dbml")
    bundle = load_mapping(tmp_path / "m.yaml")
    keys = {r.key for r in derive_requirements(schema, bundle, "default")}
    assert "manage_permissions_bit" not in keys
    assert "process_query" not in keys
    assert "sealed_surface" not in keys
    t = assess_targets(schema, bundle, "default")
    assert t["list_titles"] == ["APP_Risk"]
    assert t["base_templates"] == [100]
    assert t["declares_groups"] is False


def test_styled_pack_requirements(tmp_path: Path) -> None:
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Risk {\n  Id int [pk, increment]\n  Title nvarchar [not null]\n}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Risk: { kind: List, base_template: 100, site_role: default }\n"
        "seal_columns: true\n"
        "prevent_list_deletion: true\n"
        "versioning: { default: { enable_versioning: true, major_version_limit: 500, "
        "enable_minor_versions: false } }\n"
        "column_formatting:\n"
        "  Risk: { Title: { style: severity, map: { a: good } } }\n"
        "groups:\n"
        "  - name: G\n    description: d\n    owner_group: 'Site Owners'\n"
        "    allow_members_edit_membership: false\n    allow_request_to_join_leave: false\n"
        "    auto_accept_request_to_join_leave: false\n"
        "    only_allow_members_view_membership: false\n",
        encoding="utf-8",
    )
    schema = parse_dbml(tmp_path / "s.dbml")
    bundle = load_mapping(tmp_path / "m.yaml")
    reqs = {r.key: r for r in derive_requirements(schema, bundle, "default")}
    assert reqs["manage_permissions_bit"].level_on_fail == "BLOCKED"
    assert reqs["process_query"].level_on_fail == "WARN"
    assert reqs["sealed_surface"].level_on_fail == "WARN"
    assert reqs["allow_deletion_surface"].level_on_fail == "WARN"
    assert reqs["custom_formatter_surface"].level_on_fail == "WARN"
    assert reqs["version_trim_mode"].level_on_fail == "WARN"


def _assess_js() -> str:
    from dbml_sharepoint.assessgen import generate_assess_js
    from dbml_sharepoint.release import load_release
    schema, bundle = _simple()
    return generate_assess_js(
        schema=schema, bundle=bundle,
        release=load_release(FIXTURES / "release.yaml"),
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default", source_dbml="simple.dbml",
        generated_at="2026-05-04T00:00:00Z",
    )


def test_assess_is_read_only() -> None:
    import re
    js = _assess_js()
    assert "'X-HTTP-Method'" not in js and '"X-HTTP-Method"' not in js
    posts = re.findall(r"method:\s*'POST'", js)
    for m in re.finditer(r"method:\s*'POST'", js):
        window = js[max(0, m.start() - 400): m.start() + 400]
        assert any(tok in window for tok in
                   ("contextinfo", "ProcessQuery", "GetSiteScriptFromWeb")), window
    assert posts, "expected at least the contextinfo POST"


def test_assess_tier1_probes_present() -> None:
    js = _assess_js()
    assert "GetAvailableTagsForSite" in js
    assert "EffectiveBasePermissions" in js
    assert "web/listtemplates" in js.lower()
    assert "ReadOnly" in js and "LockIssue" in js
    assert "WebTemplate" in js
    assert "[SP-ASSESS]" in js
    assert "apiUrl" in js and "odataName" in js


def test_assess_derived_probes_present() -> None:
    js = _assess_js()
    assert "APP_Project" in js and "APP_Task" in js
    assert "list_template_100" in js
    assert "_spPageContextInfo" in js
    assert "site-mismatch" in js


def test_assess_verdict_line() -> None:
    js = _assess_js()
    assert "COMPATIBLE" in js and "DEGRADED" in js and "BLOCKED" in js
    assert "pack:" in js


def test_assess_manifest_lists_requirements_and_honesty() -> None:
    from dbml_sharepoint.assessgen import generate_assess_manifest
    schema, bundle = _simple()
    md = generate_assess_manifest(
        schema=schema, bundle=bundle,
        site_url="https://x.sharepoint.com/sites/t", site_role="default",
    )
    assert "# Site assessment" in md
    assert "manage_lists_bit" in md
    assert "APP_Project" in md
    assert "## Not assessable" in md
    assert "Power Automate" in md


def test_assess_header_carries_full_provenance() -> None:
    """Same traceability contract as deploy.js/rollback.js headers."""
    js = _assess_js()
    assert "Release tag:  0.1.0-test" in js
    assert "Schema:       v0.8" in js
    assert "Deployer:     vdbml-sharepoint/0.1.0" in js
    assert "Generated at: 2026-05-04T00:00:00Z" in js
