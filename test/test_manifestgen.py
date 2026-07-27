# test/test_manifestgen.py
from pathlib import Path
from typing import Any, ClassVar

from dbml_sharepoint.analysis.phases import phase_number as pn
from dbml_sharepoint.analysis.validator import validate, validate_against_mapping
from dbml_sharepoint.extension import BaseExtension, ManifestExtras, SiteContext
from dbml_sharepoint.generators.jsgen import build_schema_json
from dbml_sharepoint.generators.manifestgen import generate_manifest
from dbml_sharepoint.model.mapping_loader import load_mapping
from dbml_sharepoint.model.parser import parse_dbml
from dbml_sharepoint.model.release import load_release

FIXTURES = Path(__file__).parent / "fixtures"


def test_manifest_includes_phase_headings_and_release() -> None:
    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    release = load_release(FIXTURES / "release.yaml")
    findings = validate(schema) + validate_against_mapping(schema, bundle)
    schema_json = build_schema_json(schema, bundle, "default")

    md = generate_manifest(
        schema_json=schema_json,
        findings=findings,
        bundle=bundle,
        release=release,
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default",
        source_dbml="simple.dbml",
        source_mtime="2026-05-04T00:00:00Z",
        generated_at="2026-05-04T00:00:00Z",
    )

    assert f"Phase {pn('lists')}" in md
    assert f"Phase {pn('lookups')}" in md
    assert f"Phase {pn('indexes')}" in md
    assert "0.1.0-test" in md
    assert "Supported deployment mode" in md
    assert "clean first provision" in md
    assert "not evidence of a" in md
    assert "general in-place schema upgrade" in md
    assert "Keep the site" in md and "inactive" in md
    assert "Retention policy mapping (desired state only)" in md
    assert "No retention labels are applied by `deploy.js`" in md
    assert "desired-state deployment evidence only" in md
    assert "a tenant administrator" in md
    assert "must prove the approved per-library and per-item mechanism" in md
    assert "before live data" in md
    assert "scoped exception/alternative process" in md
    assert "applied retroactively when admin access becomes available" not in md
    assert "Must be empty at deploy" in md
    assert "List Maintainer | Site Owners | yes" in md
    # Ownership: automated CSOM correction first, fail-closed manual fallback.
    assert "read-only `/owner` resource" in md
    assert "CSOM `ProcessQuery` owner assignment" in md
    assert "Site permissions" in md
    assert "rerun the same generated script" in md
    assert "never removes membership automatically" in md
    assert "isolated as" in md and f"Phase {pn('lists')}" in md
    assert "copyRoleAssignments=false" in md
    assert "clearSubscopes=false" in md


class _SeedExtension(BaseExtension):
    name: ClassVar[str] = "seedstub"

    def seed_lists(
        self, bundle: Any, schema: Any, site_context: SiteContext,
    ) -> dict[str, dict[str, Any]]:
        return {"APP_AppSettings": {"Title": "App Settings", "UnitName": "Zeta"}}

    def manifest_extras(self, bundle: Any, schema: Any) -> ManifestExtras:
        return ManifestExtras(
            sections={"Organisation identity": "Seeded from the organisation register."},
            warnings=["No register match for site https://x — TBD placeholders used."],
        )


def test_manifest_renders_seed_items_and_extension_extras() -> None:
    """The generalized manifest shows a data-driven 'Seed items' section plus
    the active extension's ManifestExtras sections and warnings."""
    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    release = load_release(FIXTURES / "release.yaml")
    ext = _SeedExtension()
    schema_json = build_schema_json(
        schema, bundle, "default",
        site_url="https://example.sharepoint.com/sites/t1",
        release=release, extension=ext,
    )

    md = generate_manifest(
        schema_json=schema_json,
        findings=[],
        bundle=bundle,
        release=release,
        site_url="https://example.sharepoint.com/sites/t1",
        site_role="default",
        source_dbml="simple.dbml",
        source_mtime="2026-05-04T00:00:00Z",
        generated_at="2026-05-04T00:00:00Z",
        manifest_extras=ext.manifest_extras(bundle, schema),
    )

    assert "## Seed items" in md
    assert "APP_AppSettings" in md
    assert "Zeta" in md
    assert "existing singleton must match exactly" in md
    assert "sole row" in md
    assert "newly inserted seed is" in md and "re-read" in md
    assert "## Organisation identity" in md
    assert "Seeded from the organisation register." in md
    assert "## Extension warnings" in md
    assert "TBD placeholders used." in md


def test_manifest_carries_operator_run_instructions() -> None:
    """The manifest is the operator's document: it must explain where and how
    to run deploy.js (classic page, console, expected output), not just what
    the deployment contains."""
    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    release = load_release(FIXTURES / "release.yaml")
    schema_json = build_schema_json(schema, bundle, "default")
    md = generate_manifest(
        schema_json=schema_json,
        findings=[],
        bundle=bundle,
        release=release,
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default",
        source_dbml="simple.dbml",
        source_mtime="2026-05-04T00:00:00Z",
        generated_at="2026-05-04T00:00:00Z",
    )
    assert "## How to run this deployment" in md
    assert "/_layouts/15/settings.aspx" in md
    assert "allow pasting" in md
    assert "[SP-DEPLOY]" in md
    assert "ProcessQuery" in md  # automated owner correction described


def test_manifest_describes_operator_self_enrolment(tmp_path: Path) -> None:
    (tmp_path / "m.yaml").write_text(
        (FIXTURES / "calculated-mapping.yaml").read_text(encoding="utf-8")
        + (
            "\ngroups:\n"
            "  - name: GH List Administrators\n"
            "    description: Test admin group\n"
            "    owner_group: Site Owners\n"
            "    allow_members_edit_membership: false\n"
            "    allow_request_to_join_leave: false\n"
            "    auto_accept_request_to_join_leave: false\n"
            "    only_allow_members_view_membership: false\n"
            "    enroll_operator_during_deploy: true\n"
        ),
        encoding="utf-8",
    )
    schema = parse_dbml(FIXTURES / "calculated.dbml")
    bundle = load_mapping(tmp_path / "m.yaml")
    release = load_release(FIXTURES / "release.yaml")
    schema_json = build_schema_json(schema, bundle, "default")
    md = generate_manifest(
        schema_json=schema_json,
        findings=[],
        bundle=bundle,
        release=release,
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default",
        source_dbml="calculated.dbml",
        source_mtime="2026-05-04T00:00:00Z",
        generated_at="2026-05-04T00:00:00Z",
    )
    assert "Operator self-enrol" in md
    assert "removed automatically at the end of the run" in md


def test_manifest_lists_declared_views(tmp_path: Path) -> None:
    """Declared views are review material like fields and ACLs: the manifest
    must show, per view, its list, curated columns, filter/sort/group shape
    and which view takes the default slot, plus a Summary count."""
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Enum status {\n"
        '  "Open"\n'
        '  "Closed"\n'
        "}\n"
        "Table Risk {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar [not null]\n"
        "  Status status\n"
        "  DueDate date\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Risk: { kind: List, base_template: 100, site_role: default }\n"
        "views:\n"
        "  Risk:\n"
        "    - title: Open risks\n"
        "      default: true\n"
        "      fields: [Title, Status, DueDate]\n"
        "      where:\n"
        "        - { field: Status, op: neq, value: Closed }\n"
        "      sort:\n"
        "        - { field: DueDate, direction: asc }\n",
        encoding="utf-8",
    )
    schema = parse_dbml(tmp_path / "s.dbml")
    bundle = load_mapping(tmp_path / "m.yaml")
    release = load_release(FIXTURES / "release.yaml")
    schema_json = build_schema_json(schema, bundle, "default")
    md = generate_manifest(
        schema_json=schema_json,
        findings=[],
        bundle=bundle,
        release=release,
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default",
        source_dbml="s.dbml",
        source_mtime="2026-05-04T00:00:00Z",
        generated_at="2026-05-04T00:00:00Z",
    )
    assert f"## Phase {pn('views')}: views" in md
    assert "- Views to provision: 1" in md
    assert "**Open risks** on APP_Risk (default)" in md
    assert "Title, Status, DueDate" in md
    assert "undeclared views are never modified" in md


def test_manifest_view_bullets_render_one_per_line(tmp_path: Path) -> None:
    """trim_blocks eats the newline after a line-terminal {% endif %}, which
    concatenated every view bullet into one run-on line."""
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Risk {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar [not null]\n"
        "  DueDate date\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Risk: { kind: List, base_template: 100, site_role: default }\n"
        "views:\n"
        "  Risk:\n"
        "    - title: First\n"
        "      fields: [Title]\n"
        "    - title: Second\n"
        "      fields: [DueDate]\n",
        encoding="utf-8",
    )
    schema = parse_dbml(tmp_path / "s.dbml")
    bundle = load_mapping(tmp_path / "m.yaml")
    release = load_release(FIXTURES / "release.yaml")
    md = generate_manifest(
        schema_json=build_schema_json(schema, bundle, "default"),
        findings=[],
        bundle=bundle,
        release=release,
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default",
        source_dbml="s.dbml",
        source_mtime="2026-05-04T00:00:00Z",
        generated_at="2026-05-04T00:00:00Z",
    )
    assert "\n- **First** on APP_Risk: Title\n" in md
    assert "\n- **Second** on APP_Risk: DueDate\n" in md


def test_manifest_lists_column_formatting(tmp_path: Path) -> None:
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Risk {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar [not null]\n"
        "  Score int\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Risk: { kind: List, base_template: 100, site_role: default }\n"
        "column_formatting:\n"
        "  Risk:\n"
        "    Score: { elmType: div }\n",
        encoding="utf-8",
    )
    schema = parse_dbml(tmp_path / "s.dbml")
    bundle = load_mapping(tmp_path / "m.yaml")
    md = generate_manifest(
        schema_json=build_schema_json(schema, bundle, "default"),
        findings=[],
        bundle=bundle,
        release=load_release(FIXTURES / "release.yaml"),
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default",
        source_dbml="s.dbml",
        source_mtime="2026-05-04T00:00:00Z",
        generated_at="2026-05-04T00:00:00Z",
    )
    assert "## Column formatting" in md
    assert "- APP_Risk.Score" in md
    assert "- Formatted columns: 1" in md


def test_manifest_lists_form_formatting(tmp_path: Path) -> None:
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Risk {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar [not null]\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Risk: { kind: List, base_template: 100, site_role: default }\n"
        "form_formatting:\n"
        "  Risk:\n"
        "    header: { elmType: div }\n"
        "    body: { sections: [ { displayname: X, fields: [Title] } ] }\n",
        encoding="utf-8",
    )
    schema = parse_dbml(tmp_path / "s.dbml")
    bundle = load_mapping(tmp_path / "m.yaml")
    md = generate_manifest(
        schema_json=build_schema_json(schema, bundle, "default"),
        findings=[],
        bundle=bundle,
        release=load_release(FIXTURES / "release.yaml"),
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default",
        source_dbml="s.dbml",
        source_mtime="2026-05-04T00:00:00Z",
        generated_at="2026-05-04T00:00:00Z",
    )
    assert "## Form formatting" in md
    assert "- APP_Risk: header, body" in md


def test_manifest_run_order_puts_assessment_first() -> None:
    """The bundle's run sequence: assess (read-only, verdict gate) →
    manifest review → deploy paste → verify → rollback only for a failed
    first provision."""
    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    release = load_release(FIXTURES / "release.yaml")
    schema_json = build_schema_json(schema, bundle, "default")
    md = generate_manifest(
        schema_json=schema_json,
        findings=[],
        bundle=bundle,
        release=release,
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default",
        source_dbml="simple.dbml",
        source_mtime="2026-05-04T00:00:00Z",
        generated_at="2026-05-04T00:00:00Z",
    )
    run = md[md.index("## How to run this deployment"): md.index("## Summary")]
    # Assessment gates the deploy paste.
    assert run.index("assess.js") < run.index("deploy.js")
    assert "COMPATIBLE" in run
    assert "assess-manifest.md" in run
    # Verification and the rollback scope limit close the sequence.
    assert "verification checklist" in run
    assert run.index("[SP-DEPLOY]") < run.index("rollback.js")
    assert "failed FIRST provision" in run


# --- The manifest's three blind spots ---------------------------------------


def _manifest_for(tmp_path: Path, section: str) -> str:
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Escalation {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar [not null]\n"
        "  Note nvarchar\n"
        "  Status nvarchar\n"
        "  Parent int [ref: > Escalation.Id]\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Escalation: { kind: List, base_template: 100, site_role: default }\n" + section,
        encoding="utf-8",
    )
    schema = parse_dbml(tmp_path / "s.dbml")
    bundle = load_mapping(tmp_path / "m.yaml")
    return generate_manifest(
        schema_json=build_schema_json(schema, bundle, "default"),
        findings=[],
        bundle=bundle,
        release=load_release(FIXTURES / "release.yaml"),
        site_url="https://example.sharepoint.com/sites/t",
        site_role="default",
        source_dbml="s.dbml",
        source_mtime="2026-05-04T00:00:00Z",
        generated_at="2026-05-04T00:00:00Z",
    )


def test_manifest_reports_a_declaration_on_a_deferred_lookup(tmp_path: Path) -> None:
    """The sections iterated fields_phase1 only, while jsgen puts the same
    keys on phase2_lookups and deploy.js writes them. So a declaration on a
    self-referencing lookup deployed and the review artefact denied it —
    the inverse of the silent-drop bug, and just as misleading."""
    md = _manifest_for(
        tmp_path,
        "form_visibility:\n"
        "  Escalation:\n"
        "    reconcile: declared\n"
        "    columns:\n"
        "      Parent: hidden\n",
    )
    assert "APP_Escalation.Parent" in md


def test_manifest_reports_the_column_validation_reconcile_mode(tmp_path: Path) -> None:
    """reconcile was reported for form_visibility only, so a
    column_validation block running the default `exact` cleared every
    undeclared column's rule with no mode shown anywhere."""
    md = _manifest_for(
        tmp_path,
        "column_validation:\n"
        "  Escalation:\n"
        "    columns:\n"
        "      Note:\n"
        "        when:\n"
        "          - { field: Note, op: is_not_null }\n"
        "        message: Say something.\n",
    )
    section = md.split("## Column validation")[1].split("##")[0]
    assert "exact" in section, section


def test_manifest_has_a_list_validation_section(tmp_path: Path) -> None:
    """Both siblings had a section; the cross-column one had none, so a
    save rule governing the whole list was deployed unannounced."""
    md = _manifest_for(
        tmp_path,
        "list_validation:\n"
        "  Escalation:\n"
        "    when:\n"
        "      - { field: Status, op: is_not_null }\n"
        "    message: A status is required.\n",
    )
    assert "## List validation" in md
    assert "A status is required." in md
    assert "Status is_not_null" in md


def test_manifest_lists_retired_columns(tmp_path: Path) -> None:
    """The operator must be able to see, from the manifest alone, which
    columns are retired and why — retirement is a silent mutation of the
    author's own declarations."""
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Enum rag {\n"
        '  "Green"\n'
        '  "Amber"\n'
        "}\n"
        "Table Board {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar\n"
        "  BoardDate date\n"
        "  OperationsStatus rag\n"
        "  SiteServicesStatus rag\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Board: { kind: List, base_template: 100, site_role: default }\n"
        "display_names:\n"
        "  mode: auto\n"
        "retired_columns:\n"
        "  Board:\n"
        "    OperationsStatus:\n"
        "      retired: 2026-09-01\n"
        "      superseded_by: SiteServicesStatus\n"
        '      reason: "Merged into Site Services"\n',
        encoding="utf-8",
    )
    schema = parse_dbml(tmp_path / "s.dbml")
    bundle = load_mapping(tmp_path / "m.yaml")
    md = generate_manifest(
        schema_json=build_schema_json(schema, bundle, "default"),
        findings=[],
        bundle=bundle,
        release=load_release(FIXTURES / "release.yaml"),
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default",
        source_dbml="s.dbml",
        source_mtime="2026-07-27T00:00:00Z",
        generated_at="2026-07-27T00:00:00Z",
    )

    assert "## Retired columns" in md
    assert (
        "| APP_Board | OperationsStatus | Operations Status (retired) | "
        "2026-09-01 | SiteServicesStatus | Merged into Site Services |"
    ) in md
    assert "Never delete them from the DBML" in md


def test_manifest_omits_retired_section_when_nothing_is_retired() -> None:
    """Absent entirely, not an empty table — the manifest is read by
    operators, not diffed by machines."""
    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    md = generate_manifest(
        schema_json=build_schema_json(schema, bundle, "default"),
        findings=[],
        bundle=bundle,
        release=load_release(FIXTURES / "release.yaml"),
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default",
        source_dbml="simple.dbml",
        source_mtime="2026-07-27T00:00:00Z",
        generated_at="2026-07-27T00:00:00Z",
    )
    assert "Retired columns" not in md
