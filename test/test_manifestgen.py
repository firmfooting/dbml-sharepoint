# test/test_manifestgen.py
from dataclasses import replace
from pathlib import Path
from typing import Any, ClassVar, Unpack

from _builders import ID_PK, TITLE, table
from _model import MappingSections, column, enum, ref
from _model import bundle as make_bundle
from _model import schema as make_schema
from _model import table as make_table
from _packs import blocks, entities, entity, pack, write_mapping
from _paths import FIXTURES

from dbml_sharepoint.analysis.phases import phase_number as pn
from dbml_sharepoint.analysis.validator import validate, validate_against_mapping
from dbml_sharepoint.extension import BaseExtension, ManifestExtras, SiteContext
from dbml_sharepoint.generators.jsgen import build_schema_json
from dbml_sharepoint.generators.manifestgen import generate_manifest
from dbml_sharepoint.model.conditions import Group, Leaf
from dbml_sharepoint.model.mapping_loader import (
    ColumnValidation,
    EntityMapping,
    EntitySection,
    FormFormatting,
    FormVisibility,
    ListValidation,
    ViewDef,
    ViewSort,
    load_mapping,
)
from dbml_sharepoint.model.parser import parse_dbml
from dbml_sharepoint.model.release import load_release


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
    assert "No retention labels are applied by `deploy.js.txt`" in md
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
            warnings=["No register match for site https://x; TBD placeholders used."],
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
    to run deploy.js.txt (classic page, console, expected output), not just what
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
    # Stays on the filesystem: the input is a FIXTURE with one block appended,
    # so the text on disk is the thing being varied.
    #
    # `prefix=None`: the fixture carries its own. The old form prepended "\n"
    # to guard against the fixture not ending in one; `blocks` normalises every
    # part to exactly one trailing newline, so that guard is now structural.
    write_mapping(
        tmp_path,
        blocks(
            (FIXTURES / "calculated-mapping.yaml").read_text(encoding="utf-8"),
            """
            groups:
              - name: GH List Administrators
                description: Test admin group
                owner_group: Site Owners
                allow_members_edit_membership: false
                allow_request_to_join_leave: false
                auto_accept_request_to_join_leave: false
                only_allow_members_view_membership: false
                enroll_operator_during_deploy: true
            """,
        ),
        prefix=None,
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
    assert "Enrolled by this deploy" in md
    assert "you (the operator), removed automatically at the end of the run" in md


def _reader_manifest(enterprise_reader: str | None) -> str:
    """The manifest for a mapping that declares an enterprise-reader group,
    built with and without the flag."""
    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping-with-reader.yaml")
    release = load_release(FIXTURES / "release.yaml")
    return generate_manifest(
        schema_json=build_schema_json(schema, bundle, "default"),
        findings=[],
        bundle=bundle,
        release=release,
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default",
        source_dbml="simple.dbml",
        source_mtime="2026-05-04T00:00:00Z",
        generated_at="2026-05-04T00:00:00Z",
        enterprise_reader=enterprise_reader,
    )


def test_the_manifest_names_a_list_the_reader_group_is_not_granted_on() -> None:
    """The unconditional "reads every list" promise was not verified.

    `permissions_for_entity` resolves an override INSTEAD of the default
    policy, and an override carries its own complete assignment list -- so a
    mapping may grant the reader on the default and leave it out of one
    override. `_levels_granted_to_group`'s docstring records that the
    validator permits this deliberately, because an override exists to
    differ. The manifest then told an operator the reporting account had
    fleet-wide read while one list was silently unreadable.

    Built by taking the reader fixture and dropping the reader from ONE
    list's override, so the only thing that changed is the fact under test.
    """
    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping-with-reader.yaml")
    perms = bundle.mapping.permissions
    assert perms is not None
    reader_group = next(g.name for g in perms.groups if g.enroll_enterprise_reader)

    entity = next(iter(bundle.mapping.entities))
    default = perms.default_policy
    assert default is not None
    perms.overrides[entity] = replace(
        default,
        assignments=[
            a for a in default.assignments
            if not (a.principal.kind == "group" and a.principal.name == reader_group)
        ],
    )

    manifest = generate_manifest(
        schema_json=build_schema_json(schema, bundle, "default"),
        findings=[],
        bundle=bundle,
        release=load_release(FIXTURES / "release.yaml"),
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default",
        source_dbml="simple.dbml",
        source_mtime="2026-05-04T00:00:00Z",
        generated_at="2026-05-04T00:00:00Z",
        enterprise_reader=None,
    )
    excluded = f"{bundle.mapping.prefix}{entity}"
    assert excluded in manifest, manifest
    assert "EXCEPT" in manifest, manifest


def test_the_manifest_claims_every_list_when_every_block_grants_the_reader(
) -> None:
    """The complement, so the qualification cannot fire for everything.

    Every shipped family grants the reader on every block -- pinned by
    `test_the_reader_group_is_granted_read_on_every_policy_block` -- so the
    common case must keep reading as it did.
    """
    # Collapsed, because the claim is hard-wrapped into the paragraph and a
    # raw substring would be asserting about where the line happens to break.
    manifest = " ".join(_reader_manifest(None).split())
    assert "read every list this bundle provisions" in manifest, manifest
    assert "EXCEPT" not in manifest


def test_manifest_warns_that_the_reader_enrolment_is_permanent() -> None:
    """The manifest is what an operator reads BEFORE pasting anything, so it
    is the only place this warning can do its work.

    The reader enrolment is the one thing the bundle does that `rollback.js.
    txt` does not undo: roll back and the lists are gone, while the group
    and the named account in it survive. `emit_bundle` passed
    `enterprise_reader` to `generate_deploy_js` alone, so the manifest could
    not say any of this -- the operator's review artefact was silent about
    the single irreversible act in the run.
    """
    md = _reader_manifest("svc-reporting@example.org")

    assert "svc-reporting@example.org" in md
    assert "Enterprise Reader" in md          # the group it goes into
    assert "PERMANENT" in md
    assert f"Phase {pn('reader_enrolment')}" in md
    # And the rollback consequence, in as many words.
    assert "does not delete the group" in md
    assert "nothing left for it to read" in md


def test_manifest_says_the_reader_group_is_empty_without_the_flag() -> None:
    """The mirror. A build with no `--enterprise-reader` still creates the
    group, and an operator who reads only the group table needs to know it
    is created empty -- otherwise the row looks like an enrolment nobody
    asked for. Without this the permanent-membership assertions above would
    pass on a template that printed the warning unconditionally.
    """
    md = _reader_manifest(None)

    assert "created empty" in md
    assert "PERMANENT" not in md
    assert "svc-reporting@example.org" not in md


def test_the_group_table_never_reports_the_reader_group_as_unenrolled() -> None:
    """The defect this pins: the table's last column asked only about
    OPERATOR self-enrolment and answered a flat "no" for the enterprise-
    reader group -- the one group this deploy permanently adds an account
    to. A reviewer scanning the column read "nothing is added here" about
    the row where something is.

    Asserted on the ROW rather than on the document, because the file also
    contains rows that legitimately say nobody.
    """
    row = next(
        line for line in _reader_manifest("svc-reporting@example.org").splitlines()
        if line.startswith("| Enterprise Reader |")
    )

    assert "svc-reporting@example.org" in row
    assert "PERMANENT" in row
    assert "nobody" not in row


def test_the_group_table_marks_the_reader_group_empty_without_the_flag() -> None:
    """Same row, no flag: it must say nobody is enrolled AND why, so the
    reader cannot be mistaken for a group the deploy simply ignores."""
    row = next(
        line for line in _reader_manifest(None).splitlines()
        if line.startswith("| Enterprise Reader |")
    )

    assert "nobody" in row
    assert "--enterprise-reader" in row
    assert "PERMANENT" not in row


def test_a_mapping_with_no_reader_group_gets_no_reader_prose() -> None:
    """No group, no paragraph. The narrative is driven off the declared
    group, not off the flag, so a mapping that declares neither must not
    grow a section about a group it does not have."""
    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    release = load_release(FIXTURES / "release.yaml")
    md = generate_manifest(
        schema_json=build_schema_json(schema, bundle, "default"),
        findings=[],
        bundle=bundle,
        release=release,
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default",
        source_dbml="simple.dbml",
        source_mtime="2026-05-04T00:00:00Z",
        generated_at="2026-05-04T00:00:00Z",
    )

    assert "Enterprise reader" not in md
    assert "created empty" not in md


def test_manifest_lists_declared_views() -> None:
    """Declared views are review material like fields and ACLs: the manifest
    must show, per view, its list, curated columns, filter/sort/group shape
    and which view takes the default slot, plus a Summary count."""
    schema = make_schema(
        make_table(
            "Risk",
            column("Title", required=True),
            column("Status", "status"),
            column("DueDate", "date"),
        ),
        enums=[enum("status", "Open", "Closed")],
    )
    bundle = make_bundle(
        entities=["Risk"],
        views={"Risk": [
            ViewDef(
                title="Open risks",
                fields=["Title", "Status", "DueDate"],
                default=True,
                where=Group("all_of", (Leaf(field="Status", op="neq", value="Closed"),)),
                sort=[ViewSort(field="DueDate", direction="asc")],
            ),
        ]},
    )
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
    assert "- Views to provision: 2" in md
    assert "- **All Items** on APP_Risk [hidden]" in md
    assert "**Open risks** on APP_Risk (default)" in md
    assert "Title, Status, DueDate" in md
    assert "other views are" in md and "never modified" in md


def test_manifest_view_bullets_render_one_per_line() -> None:
    """trim_blocks eats the newline after a line-terminal {% endif %}, which
    concatenated every view bullet into one run-on line."""
    schema = make_schema(
        make_table("Risk", column("Title", required=True), column("DueDate", "date")),
    )
    bundle = make_bundle(
        entities=["Risk"],
        views={"Risk": [
            ViewDef(title="First", fields=["Title"]),
            ViewDef(title="Second", fields=["DueDate"]),
        ]},
    )
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


def test_manifest_lists_column_formatting() -> None:
    schema = make_schema(
        make_table("Risk", column("Title", required=True), column("Score", "int")),
    )
    bundle = make_bundle(
        entities=["Risk"],
        column_formatting={"Risk": {"Score": {"elmType": "div"}}},
    )
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


def test_manifest_lists_form_formatting() -> None:
    schema = make_schema(make_table("Risk", column("Title", required=True)))
    bundle = make_bundle(
        entities=["Risk"],
        form_formatting={"Risk": FormFormatting(
            header={"elmType": "div"},
            body={"sections": [{"displayname": "X", "fields": ["Title"]}]},
        )},
    )
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
    assert run.index("assess.js.txt") < run.index("deploy.js.txt")
    assert "COMPATIBLE" in run
    assert "assess-manifest.md" in run
    # Verification and the rollback scope limit close the sequence.
    assert "verification checklist" in run
    assert run.index("[SP-DEPLOY]") < run.index("rollback.js.txt")
    assert "failed FIRST provision" in run


# --- The manifest's three blind spots ---------------------------------------


def _manifest_for(**sections: Unpack[MappingSections]) -> str:
    """The standard Escalation entity, plus whatever mapping sections the test
    declares.

    `**sections` goes straight through to the mapping builder, so a misspelled
    section name is a type error rather than a block the loader would once
    have rejected at run time.
    """
    schema = make_schema(make_table(
        "Escalation",
        column("Title", required=True),
        column("Note"),
        column("Status"),
        ref("Parent", "Escalation.Id"),
    ))
    bundle = make_bundle(entities=["Escalation"], **sections)
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


def test_manifest_reports_a_declaration_on_a_deferred_lookup() -> None:
    """The sections iterated fields_phase1 only, while jsgen puts the same
    keys on phase2_lookups and deploy.js.txt writes them. So a declaration on a
    self-referencing lookup deployed and the review artefact denied it, the
    inverse of the silent-drop bug, and just as misleading."""
    md = _manifest_for(form_visibility={
        "Escalation": EntitySection(
            reconcile="declared",
            # `Parent: hidden` is the loader's shorthand for both flags off.
            columns={"Parent": FormVisibility(new=False, existing=False)},
        ),
    })
    assert "APP_Escalation.Parent" in md


def test_manifest_reports_the_column_validation_reconcile_mode() -> None:
    """reconcile was reported for form_visibility only, so a
    column_validation block running the default `exact` cleared every
    undeclared column's rule with no mode shown anywhere."""
    md = _manifest_for(column_validation={
        "Escalation": EntitySection(columns={
            "Note": ColumnValidation(
                when=Group("all_of", (Leaf(field="Note", op="is_not_null"),)),
                message="Say something.",
            ),
        }),
    })
    section = md.split("## Column validation")[1].split("##")[0]
    assert "exact" in section, section


def test_manifest_has_a_list_validation_section() -> None:
    """Both siblings had a section; the cross-column one had none, so a
    save rule governing the whole list was deployed unannounced."""
    md = _manifest_for(list_validation={
        "Escalation": ListValidation(
            when=Group("all_of", (Leaf(field="Status", op="is_not_null"),)),
            message="A status is required.",
        ),
    })
    assert "## List validation" in md
    assert "A status is required." in md
    assert "Status is_not_null" in md


def test_manifest_covers_only_the_lists_this_role_deploys(tmp_path: Path) -> None:
    """The manifest is what an operator reads to decide whether to paste the
    script, so it must describe THIS build and no other.

    `schema_json` is already filtered to the target `site_role`, but several
    inventories iterated `bundle.mapping` directly instead, so a build for
    role `default` announced validation rules, retirements, reconcile modes
    and polymorphic columns on lists that appear nowhere in its own
    `deploy.js.txt`. Not a deploy defect; the manifest-disagrees-with-behaviour
    one, which is worse in an artefact whose whole job is to be believed."""
    # Ledger lives on the OTHER role, and every section below names it.
    # Escalation carries a declaration in the two reconcile-bearing sections
    # so those sections RENDER: their "Reconcile:" line is emitted only when
    # the section has entries, which would otherwise hide the same leak.
    #
    # Stays on the filesystem: `retired_columns` is FOLDED by the loader
    # (`_apply_retirement`) into `form_visibility` and
    # `display_name_overrides`, and those derived entries are extra places
    # "Ledger" could leak. Building the mapping as objects would skip the
    # fold, quietly shrinking what this test covers. See `_model.mapping`,
    # which has no way to run it.
    schema, bundle = pack(
        tmp_path,
        dbml=blocks(
            table("Escalation", ID_PK, TITLE, "Note nvarchar", "Status nvarchar"),
            table(
                "Ledger", ID_PK, TITLE,
                "Note nvarchar", "Status nvarchar", "OldNote nvarchar",
            ),
        ),
        mapping=blocks(
            "\n".join([
                "entities:",
                entity("Escalation"),
                entity("Ledger", site_role="finance"),
            ]),
            """
            display_names:
              mode: auto
            form_visibility:
              Escalation:
                columns:
                  Note: hidden
              Ledger:
                columns:
                  Note: hidden
            column_validation:
              Escalation:
                columns:
                  Note:
                    when:
                      - { field: Note, op: is_not_null }
                    message: Say something.
              Ledger:
                columns:
                  Note:
                    when:
                      - { field: Note, op: is_not_null }
                    message: Say something.
            list_validation:
              Ledger:
                when:
                  - { field: Status, op: is_not_null }
                message: A status is required.
            retired_columns:
              Ledger:
                OldNote:
                  retired: 2026-09-01
            polymorphic_patterns:
              - { list: Ledger, field: Note, discriminator: Status }
            """,
        ),
    )
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
    # Guards the fixture: a manifest that rendered nothing at all would pass
    # the real assertion below without proving anything.
    assert "APP_Escalation" in md
    leaked = [ln for ln in md.splitlines() if "APP_Ledger" in ln or "Ledger" in ln]
    assert not leaked, f"the manifest describes lists this role does not deploy: {leaked}"


def test_manifest_retention_table_covers_only_this_role() -> None:
    """The retention table is the same leak, one section further down, and
    its keys are the awkward case: `list_defaults` is authored loosely, so
    some name the entity and some the prefixed list title. Both forms must
    resolve, and a key naming no declared entity at all must SURVIVE the
    filter, because that is a typo the operator needs to see rather than a
    role leak to hide."""
    schema = make_schema(
        make_table("Escalation", column("Title", required=True)),
        make_table("Ledger", column("Title", required=True)),
    )
    bundle = make_bundle(
        entities={
            "Escalation": EntityMapping(
                name="Escalation", kind="List", base_template=100, site_role="default",
            ),
            "Ledger": EntityMapping(
                name="Ledger", kind="List", base_template=100, site_role="finance",
            ),
        },
        # The three keys are, in order: this role under its bare entity name,
        # the other role under its prefixed list title, and a key naming
        # nothing declared at all.
        retention_list_defaults={
            "Escalation": "Standard7Y",
            "APP_Ledger": "Standard7Y",
            "Ghost": "Standard7Y",
        },
    )
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
    rendered = md.split("## Retention policy mapping")[1]
    assert "| Escalation |" in rendered, rendered
    assert "| Ghost |" in rendered, rendered
    assert "Ledger" not in rendered, rendered


def test_manifest_lists_retired_columns(tmp_path: Path) -> None:
    """The operator must be able to see, from the manifest alone, which
    columns are retired and why. Retirement is a silent mutation of the
    author's own declarations.

    Stays on the filesystem: the " (retired)" display title asserted below is
    not declared anywhere, it is DERIVED by the loader's `_apply_retirement`
    fold. Handing the builders a display_name_overrides entry spelling it out
    would make the test assert its own input.
    """
    schema, bundle = pack(
        tmp_path,
        dbml=blocks("""
            Enum rag {
              "Green"
              "Amber"
            }
        """, table(
            "Board", ID_PK, "Title nvarchar",
            "BoardDate date", "OperationsStatus rag", "SiteServicesStatus rag",
        )),
        mapping=blocks(entities("Board"), """
            display_names:
              mode: auto
            retired_columns:
              Board:
                OperationsStatus:
                  retired: 2026-09-01
                  superseded_by: SiteServicesStatus
                  reason: "Merged into Site Services"
        """),
    )
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
    """Absent entirely, not an empty table. The manifest is read by
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


def test_manifest_prints_resolved_view_fields_with_set_footnote(tmp_path: Path) -> None:
    """A view declared with "@setname" must still show its RESOLVED columns
    in the manifest, plus which sets produced them. The operator reviews the
    manifest, not the mapping, and nothing may hide behind an indirection.

    Stays on the filesystem: "@setname" is resolved by the LOADER into a flat
    field list plus `expanded_sets`. A `ViewDef` built already-resolved would
    make `assert "@header" not in md` vacuous, which is the exact failure the
    test exists to catch.
    """
    schema, bundle = pack(
        tmp_path,
        dbml=table(
            "Board", ID_PK, TITLE,
            "BoardDate date", "OperationsStatus nvarchar", "WorkforceStatus nvarchar",
        ),
        mapping=blocks(entities("Board"), """
            field_sets:
              Board:
                header:   [Title, BoardDate]
                statuses: [OperationsStatus, WorkforceStatus]
            views:
              Board:
                - title: Heat grid
                  fields: ["@header", "@statuses"]
                - title: Plain
                  fields: [Title]
        """),
    )
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
    assert "Title, BoardDate, OperationsStatus, WorkforceStatus" in md
    assert "expanded from field sets: header, statuses" in md
    assert "@header" not in md
    # A view that named its columns directly carries no footnote.
    assert "**Plain** on APP_Board: Title\n" in md


def test_manifest_says_so_when_no_env_file_was_read() -> None:
    """The default `env_provenance` must say explicitly that nothing was
    read. An absent line is indistinguishable from a feature that never
    ran, and this is also the un-narrowed default `generate_manifest`'s 19
    call sites get without passing the parameter at all."""
    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    release = load_release(FIXTURES / "release.yaml")
    md = generate_manifest(
        schema_json=build_schema_json(schema, bundle, "default"),
        findings=[],
        bundle=bundle,
        release=release,
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default",
        source_dbml="simple.dbml",
        source_mtime="2026-05-04T00:00:00Z",
        generated_at="2026-05-04T00:00:00Z",
    )
    assert "**Env file:** No dbml-sharepoint.env file was read." in md


def test_manifest_reports_the_env_file_that_was_read() -> None:
    from dbml_sharepoint.model.env_file import ENV_SETTINGS, EnvProvenance, EnvValue

    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    release = load_release(FIXTURES / "release.yaml")
    provenance = EnvProvenance(
        path="dbml-sharepoint.env",
        digest="abc123def456",
        values=(
            EnvValue(setting=ENV_SETTINGS[0], value="svc@example.org", used=True, override=None),
        ),
    )
    md = generate_manifest(
        schema_json=build_schema_json(schema, bundle, "default"),
        findings=[],
        bundle=bundle,
        release=release,
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default",
        source_dbml="simple.dbml",
        source_mtime="2026-05-04T00:00:00Z",
        generated_at="2026-05-04T00:00:00Z",
        env_provenance=provenance,
    )
    assert "**Env file:** Read dbml-sharepoint.env (sha256 abc123def456)." in md
    assert "DBMLSP_ENTERPRISE_READER" in md
    assert "Field lists are shown RESOLVED" in md
