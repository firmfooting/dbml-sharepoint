# test/test_assessgen.py
from _model import bundle as make_bundle
from _model import column
from _model import schema as make_schema
from _model import table as make_table
from _paths import FIXTURES

from dbml_sharepoint.generators.assessgen import (
    assess_targets,
    derive_requirements,
)
from dbml_sharepoint.model.mapping_loader import (
    ListPermissionPolicy,
    MappingBundle,
    PermissionsConfig,
    Principal,
    RoleAssignment,
    SiteGroup,
    Versioning,
    load_mapping,
)
from dbml_sharepoint.model.parser import Schema, parse_dbml


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


def test_conditional_requirements_absent_on_bare_mapping() -> None:
    schema = make_schema(make_table("Risk", column("Title", required=True)))
    bundle = make_bundle(entities=["Risk"])
    keys = {r.key for r in derive_requirements(schema, bundle, "default")}
    assert "manage_permissions_bit" not in keys
    assert "process_query" not in keys
    assert "sealed_surface" not in keys
    t = assess_targets(schema, bundle, "default")
    assert t["list_titles"] == ["APP_Risk"]
    assert t["base_templates"] == [100]
    assert t["declares_groups"] is False


def test_styled_pack_requirements() -> None:
    # `versioning_default` is spelled out even though it repeats the loader's
    # own default: this test is about what a mapping DECLARES, and a silent
    # default would make `version_trim_mode` below look derived from nothing.
    #
    # `column_formatting` carries an inline formatter rather than the
    # `{style: severity}` shorthand the YAML form used. `derive_requirements`
    # reads only `bool(mapping.column_formatting)`, and the shorthand's whole
    # effect is the expansion the loader performs into exactly that field.
    schema = make_schema(make_table("Risk", column("Title", required=True)))
    bundle = make_bundle(
        entities=["Risk"],
        seal_columns=True,
        prevent_list_deletion=True,
        versioning_default=Versioning(
            enable_versioning=True, major_version_limit=500, enable_minor_versions=False,
        ),
        column_formatting={"Risk": {"Title": {"elmType": "div"}}},
        permissions=PermissionsConfig(
            levels=[],
            groups=[
                SiteGroup(
                    name="G",
                    description="d",
                    owner_group="Site Owners",
                    allow_members_edit_membership=False,
                    allow_request_to_join_leave=False,
                    auto_accept_request_to_join_leave=False,
                    only_allow_members_view_membership=False,
                ),
            ],
            default_policy=None,
            overrides={},
        ),
    )
    reqs = {r.key: r for r in derive_requirements(schema, bundle, "default")}
    assert reqs["manage_permissions_bit"].level_on_fail == "BLOCKED"
    assert reqs["process_query"].level_on_fail == "WARN"
    assert reqs["sealed_surface"].level_on_fail == "WARN"
    assert reqs["allow_deletion_surface"].level_on_fail == "WARN"
    assert reqs["custom_formatter_surface"].level_on_fail == "WARN"
    assert reqs["version_trim_mode"].level_on_fail == "WARN"


def test_manage_permissions_required_even_with_inheritance_left_alone() -> None:
    """#166 item 5: a per-list ACL policy that leaves inheritance intact
    (`break_inheritance: false`) still BINDS role assignments on the list, so
    it still needs ManagePermissions -- deploy.js's own preflight
    (`_field_reconcile.js.j2`) and the manifest (`manifest.md.j2`) already
    agreed on that. assess_targets used to test `declares_break_inheritance`
    instead of "a policy exists", so a mapping with zero custom permission
    levels/groups but a `break_inheritance: false` default policy made
    assess.js predict no requirement while deploy.js aborted with
    `insufficient-permissions` -- assess.js exists precisely to predict what
    deploy.js will refuse. Reproduced against the real loader with zero
    validator findings before this test was written; see the PR body for
    #166 for the full repro.

    Built-in level ("Contribute") and built-in associated group deliberately
    -- no custom `permission_levels` or `groups` declared -- so this fixture
    is the minimal one that isolates the `declares_break_inheritance` defect
    from `declares_groups`/`declares_permission_levels`, which were already
    correct.
    """
    schema = make_schema(make_table("Risk", column("Title", required=True)))
    bundle = make_bundle(
        entities=["Risk"],
        permissions=PermissionsConfig(
            levels=[],
            groups=[],
            default_policy=ListPermissionPolicy(
                break_inheritance=False,
                assignments=[
                    RoleAssignment(
                        principal=Principal(kind="associated_member_group"),
                        level="Contribute",
                    ),
                ],
            ),
            overrides={},
        ),
    )
    t = assess_targets(schema, bundle, "default")
    assert t["declares_groups"] is False
    assert t["requires_manage_permissions"] is True
    keys = {r.key for r in derive_requirements(schema, bundle, "default")}
    assert "manage_permissions_bit" in keys


def _assess_js() -> str:
    from dbml_sharepoint.generators.assessgen import generate_assess_js
    from dbml_sharepoint.model.release import load_release
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
        assert any(tok in window for tok in ("contextinfo", "ProcessQuery")), window
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
    from dbml_sharepoint.generators.assessgen import generate_assess_manifest
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
