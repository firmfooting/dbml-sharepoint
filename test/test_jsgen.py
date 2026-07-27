# test/test_jsgen.py
from pathlib import Path
from typing import Any, ClassVar

from dbml_sharepoint.analysis.phases import phase_number as pn
from dbml_sharepoint.analysis.validator import validate_all
from dbml_sharepoint.extension import BaseExtension, NullExtension, SiteContext
from dbml_sharepoint.generators.jsgen import UNMANAGED, generate_deploy_js
from dbml_sharepoint.model.mapping_loader import CrossSiteRef, MappingBundle, load_mapping
from dbml_sharepoint.model.parser import Column, Reference, Schema, parse_dbml
from dbml_sharepoint.model.release import load_release

FIXTURES = Path(__file__).parent / "fixtures"
EXPECTED = FIXTURES / "expected"

_FIXED_ARGS: dict[str, Any] = dict(
    site_url="https://example.sharepoint.com/sites/test",
    site_role="default",
    source_dbml="simple.dbml",
    source_mtime="2026-05-04T00:00:00Z",
    generated_at="2026-05-04T00:00:00Z",
)


def _generate_simple_js() -> str:
    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    release = load_release(FIXTURES / "release.yaml")
    return generate_deploy_js(schema=schema, bundle=bundle, release=release, **_FIXED_ARGS)


def test_generated_deploy_js_contains_lifecycle_markers() -> None:
    js = _generate_simple_js()

    assert "[SP-DEPLOY]" in js
    assert f"Phase {pn('lists')}" in js
    assert f"Phase {pn('lookups')}" in js
    assert f"Phase {pn('indexes')}" in js
    assert "0.1.0-test" in js  # release tag rendered


def test_simple_deploy_js_matches_golden() -> None:
    """Golden-file regression: deploy.js from simple.dbml must match
    test/fixtures/expected/simple-deploy.js byte-for-byte.

    To regenerate the golden file after a legitimate template change run::

        # from the repository root
        python -c "
        from pathlib import Path
        from dbml_sharepoint.generators.jsgen import UNMANAGED, generate_deploy_js
        from dbml_sharepoint.model.mapping_loader import load_mapping
        from dbml_sharepoint.model.parser import parse_dbml
        from dbml_sharepoint.model.release import load_release
        FIXTURES = Path('test/fixtures')
        js = generate_deploy_js(
            schema=parse_dbml(FIXTURES / 'simple.dbml'),
            bundle=load_mapping(FIXTURES / 'sharepoint-mapping.yaml'),
            release=load_release(FIXTURES / 'release.yaml'),
            site_url='https://example.sharepoint.com/sites/test',
            site_role='default',
            source_dbml='simple.dbml',
            source_mtime='2026-05-04T00:00:00Z',
            generated_at='2026-05-04T00:00:00Z',
        )
        Path('test/fixtures/expected/simple-deploy.js').write_text(js, encoding='utf-8')
        "
    """
    golden_path = EXPECTED / "simple-deploy.js"
    assert golden_path.exists(), f"Golden file missing: {golden_path}"
    golden = golden_path.read_text(encoding="utf-8")
    actual = _generate_simple_js()
    assert actual == golden, (
        "deploy.js output has changed. "
        "If the change is intentional, regenerate the golden file "
        "(see docstring above for the command)."
    )


def test_list_creation_applies_enable_minor_versions() -> None:
    """Regression: enable_minor_versions from the mapping versioning config
    was loaded but never applied. It must reach both the schema-json list
    entry and the rendered SP.List creation body."""
    from dbml_sharepoint.generators.jsgen import build_schema_json

    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    sj = build_schema_json(schema, bundle, "default")
    assert sj["lists"]
    assert all("enable_minor_versions" in lst for lst in sj["lists"])

    js = _generate_simple_js()
    assert "EnableMinorVersions" in js


def test_schema_declares_content_type_setting_for_shape_reconciliation() -> None:
    """The resume gate needs an explicit desired value, not a JS default."""
    from dbml_sharepoint.generators.jsgen import build_schema_json

    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    schema_json = build_schema_json(schema, bundle, "default")

    assert schema_json["lists"]
    assert all(lst["content_types_enabled"] is False for lst in schema_json["lists"])


def test_document_library_template_101_reaches_shape_gate() -> None:
    """Libraries must be distinguished from same-title generic lists."""
    from dbml_sharepoint.generators.jsgen import build_schema_json
    from dbml_sharepoint.model.mapping_loader import EntityMapping

    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    bundle.mapping.entities["Project"] = EntityMapping(
        name="Project",
        kind="DocumentLibrary",
        base_template=101,
        site_role="default",
    )

    project = next(
        lst for lst in build_schema_json(schema, bundle, "default")["lists"]
        if lst["title"] == "APP_Project"
    )
    assert project["base_template"] == 101


def test_boolean_default_only_emitted_when_declared() -> None:
    """Regression: the Boolean branch must only emit ``DefaultValue`` when the
    DBML column actually declares a default. Previously it unconditionally
    wrote ``"0"`` for unset booleans (``None`` is falsy in the ternary),
    silently forcing optional booleans to default to false and erasing the
    null-vs-false distinction downstream flows may rely on.
    """
    from dbml_sharepoint.generators.jsgen import _field_body

    no_default = _field_body(Column(name="QuorumMet", type="boolean"), {}, "APP_")
    assert no_default is not None
    assert "DefaultValue" not in no_default["body"]

    # NB: keep as a list — a dict would collapse False/0 and True/1 into one
    # key each (Python treats them as equal), hiding the int cases.
    cases: list[tuple[str | int | bool, str]] = [
        (False, "0"),
        (True, "1"),
        (0, "0"),
        (1, "1"),
    ]
    for declared, expected in cases:
        field = _field_body(
            Column(name="Flag", type="boolean", default=declared), {}, "APP_",
        )
        assert field is not None
        assert field["body"]["DefaultValue"] == expected, (declared, expected)


def test_text_default_is_emitted_when_declared() -> None:
    """Text defaults are required for provisioned, site-specific metadata.

    SharePoint applies the field default before validating a normal list-item
    create, so a build can stamp organisation constants
    without an after-create flow on every list.
    """
    from dbml_sharepoint.generators.jsgen import _field_body

    field = _field_body(
        Column(name="OrgUnitCode", type="nvarchar", default="UNIT-A"),
        {},
        "APP_",
    )
    assert field is not None
    assert field["body"]["DefaultValue"] == "UNIT-A"


def test_number_default_is_string_in_create_and_merge_shapes() -> None:
    """SP.Field.DefaultValue is String even when the field is numeric."""
    from dbml_sharepoint.generators.jsgen import _field_body, build_schema_json

    field = _field_body(Column(name="SortOrder", type="int", default=0), {}, "APP_")
    assert field is not None
    assert field["body"]["DefaultValue"] == "0"

    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    schema_json = build_schema_json(schema, bundle, "default")
    project = next(lst for lst in schema_json["lists"] if lst["title"] == "APP_Project")
    sort_order = next(
        entry for entry in project["fields_phase1"] if entry["title"] == "SortOrder"
    )
    assert sort_order["body"]["DefaultValue"] == "0"  # initial field POST
    assert {
        "list": "APP_Project",
        "field": "SortOrder",
        "metadata_type": "SP.FieldNumber",
        "default_value": "0",
    } in schema_json["field_defaults"]  # Phase 2.4 field MERGE

    js = _generate_simple_js()
    assert '"DefaultValue": "0"' in js
    assert '"default_value": "0"' in js
    assert "DefaultValue: fieldDefault.default_value" in js


def test_longtext_emits_plain_multiline_note_field() -> None:
    """Opaque connector values can exceed SharePoint URL/Text's 255 chars.

    ``longtext`` must therefore emit a plain multi-line Note field without
    silently enabling rich text or append-only history.
    """
    from dbml_sharepoint.generators.jsgen import _field_body

    field = _field_body(Column(name="JoinWebUrl", type="longtext"), {}, "APP_")

    assert field is not None
    assert field["body"] == {
        "Title": "JoinWebUrl",
        "FieldTypeKind": 3,
        "__metadata": {"type": "SP.FieldMultiLineText"},
        "RichText": False,
        "NumberOfLines": 6,
        "AppendOnly": False,
    }


def test_hyperlink_emits_field_url_display_format() -> None:
    """SP.FieldUrl writes DisplayFormat; UrlFormat is not a REST property."""
    from dbml_sharepoint.generators.jsgen import _field_body

    field = _field_body(Column(name="TermsOfReference", type="hyperlink"), {}, "APP_")

    assert field is not None
    assert field["body"] == {
        "Title": "TermsOfReference",
        "FieldTypeKind": 11,
        "__metadata": {"type": "SP.FieldUrl"},
        "DisplayFormat": 0,
    }


def test_declared_defaults_are_reconciled_on_existing_fields() -> None:
    """A skipped existing field must still receive its declared default."""
    from dbml_sharepoint.generators.jsgen import build_schema_json

    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    schema_json = build_schema_json(schema, bundle, "default")

    assert {
        "list": "APP_Project",
        "field": "Status",
        "metadata_type": "SP.FieldChoice",
        "default_value": "Open",
    } in schema_json["field_defaults"]

    js = _generate_simple_js()
    assert f"Starting Phase {pn('defaults')}: field defaults" in js
    assert "for (const fieldDefault of SCHEMA.field_defaults)" in js


def test_lookup_uses_target_display_column() -> None:
    """A1: a lookup into a target whose mapping declares display_column emits
    that field in both the desired field shape and AddField parameters, not the
    (possibly empty) built-in Title."""
    from dbml_sharepoint.generators.jsgen import _field_body
    from dbml_sharepoint.model.mapping_loader import EntityMapping

    col = Column(name="Chair", type="int", ref=Reference("Membership", "Id"))
    entities = {
        "Membership": EntityMapping(
            name="Membership", kind="List", base_template=100,
            site_role="default", display_column="DisplayName",
        ),
    }
    field = _field_body(col, {}, "APP_", entities)
    assert field is not None
    assert field["body"]["LookupField"] == "DisplayName"
    assert field["lookup_creation_parameters"] == {
        "__metadata": {"type": "SP.FieldCreationInformation"},
        "FieldTypeKind": 7,
        "Title": "Chair",
        "Required": False,
        "LookupFieldName": "DisplayName",
    }
    assert field["target_list"] == "APP_Membership"


def test_lookup_defaults_to_title_without_display_column() -> None:
    """A1: with no display_column on the target, the lookup falls back to the
    built-in Title (backward-compatible default)."""
    from dbml_sharepoint.generators.jsgen import _field_body

    col = Column(name="Project", type="int", ref=Reference("Project", "Id"))
    field = _field_body(col, {}, "APP_", {})
    assert field is not None
    assert field["body"]["LookupField"] == "Title"
    assert field["lookup_creation_parameters"]["LookupFieldName"] == "Title"


def test_immediate_lookup_uses_addfield_creation_information() -> None:
    """A normal Phase-1 lookup uses FieldCollection.AddField's exact shape."""
    from dbml_sharepoint.generators.jsgen import build_schema_json

    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    schema_json = build_schema_json(schema, bundle, "default")
    task = next(item for item in schema_json["lists"] if item["title"] == "APP_Task")
    lookup = next(field for field in task["fields_phase1"] if field["title"] == "Project")
    assert lookup["lookup_creation_parameters"] == {
        "__metadata": {"type": "SP.FieldCreationInformation"},
        "FieldTypeKind": 7,
        "Title": "Project",
        "Required": True,
        "LookupFieldName": "Title",
    }
    assert "LookupListId" not in lookup["lookup_creation_parameters"]

    js = _generate_simple_js()
    phase1 = js.split(f"Starting Phase {pn('lists')}")[1].split(
        f"Starting Phase {pn('lookups')}")[0]

    assert "...col.lookup_creation_parameters" in phase1
    assert "LookupListId: targetGuid" in phase1
    assert "/fields/addfield`" in phase1
    assert "createBody = { parameters };" in phase1
    assert "{ ...col.body, LookupList:" not in phase1
    assert "reconcileDeclaredField" in phase1


def test_deferred_circular_lookup_uses_addfield_creation_information(
    tmp_path: Path,
) -> None:
    """A circular dependency deferred to the deferred-lookups phase uses the same AddField API."""
    from dbml_sharepoint.generators.jsgen import build_schema_json

    (tmp_path / "mapping.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  A: { kind: List, base_template: 100, site_role: default }\n"
        "  B: { kind: List, base_template: 100, site_role: default }\n",
        encoding="utf-8",
    )
    schema = parse_dbml(FIXTURES / "circular.dbml")
    bundle = load_mapping(tmp_path / "mapping.yaml")
    release = load_release(FIXTURES / "release.yaml")

    schema_json = build_schema_json(schema, bundle, "default")
    assert schema_json["phase2_lookups"]
    for deferred in schema_json["phase2_lookups"]:
        parameters = deferred["field"]["lookup_creation_parameters"]
        assert parameters["__metadata"] == {
            "type": "SP.FieldCreationInformation",
        }
        assert parameters["FieldTypeKind"] == 7
        assert parameters["LookupFieldName"] == "Title"
        assert "LookupListId" not in parameters

    js = generate_deploy_js(
        schema=schema,
        bundle=bundle,
        release=release,
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default",
        source_dbml="circular.dbml",
        source_mtime="2026-05-04T00:00:00Z",
        generated_at="2026-05-04T00:00:00Z",
    )
    phase2 = js.split(f"Starting Phase {pn('lookups')}")[1].split(
        f"Starting Phase {pn('indexes')}")[0]
    assert "...lookup.field.lookup_creation_parameters" in phase2
    assert "LookupListId: targetGuid" in phase2
    assert "/fields/addfield`" in phase2
    assert "{ parameters }," in phase2
    assert "{ ...lookup.field.body, LookupList:" not in phase2
    assert "reconcileDeclaredField" in phase2


def test_self_lookup_is_deferred_with_addfield_parameters(tmp_path: Path) -> None:
    """A self-reference remains deferred and carries a complete lookup spec."""
    from dbml_sharepoint.generators.jsgen import build_schema_json

    (tmp_path / "mapping.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Node: { kind: List, base_template: 100, site_role: default }\n",
        encoding="utf-8",
    )
    schema = parse_dbml(FIXTURES / "self-ref.dbml")
    bundle = load_mapping(tmp_path / "mapping.yaml")
    release = load_release(FIXTURES / "release.yaml")
    schema_json = build_schema_json(schema, bundle, "default")

    assert len(schema_json["phase2_lookups"]) == 1
    deferred = schema_json["phase2_lookups"][0]
    assert deferred["list"] == "APP_Node"
    assert deferred["target_list"] == "APP_Node"
    assert deferred["field"]["lookup_creation_parameters"] == {
        "__metadata": {"type": "SP.FieldCreationInformation"},
        "FieldTypeKind": 7,
        "Title": "Parent",
        "Required": False,
        "LookupFieldName": "Title",
    }

    js = generate_deploy_js(
        schema=schema,
        bundle=bundle,
        release=release,
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default",
        source_dbml="self-ref.dbml",
        source_mtime="2026-05-04T00:00:00Z",
        generated_at="2026-05-04T00:00:00Z",
    )
    assert '"target_list": "APP_Node"' in js
    assert '"type": "SP.FieldCreationInformation"' in js
    assert '"LookupFieldName": "Title"' in js
    assert "/fields/addfield`" in js


def test_generated_js_uses_web_prefixed_api_urls() -> None:
    """Regression: every SP REST endpoint must be prefixed with the
    current web's server-relative URL, not a bare '/_api/...'.

    SP routes '/_api/...' against the path BEFORE '_api'. A bare
    '/_api/web/lists' targets the tenant ROOT web, not the sub-site or
    site-collection web the operator is on. The template must construct
    URLs as `${WEB}/_api/...` (where WEB is derived from
    `_spPageContextInfo.webServerRelativeUrl`).
    """
    js = _generate_simple_js()

    # Must declare WEB and an apiUrl helper.
    assert "const WEB = actualPath" in js
    assert "const apiUrl = (suffix) =>" in js
    assert "${WEB}/_api/${suffix}" in js

    # Must NOT contain any bare '/_api/' literal in fetch calls.
    # Strip comment lines (// ... or  * ...) since explanatory comments
    # describing the bug are allowed to mention the wrong form. Match
    # only string literals, which start with ' or `.
    code_lines = [
        line for line in js.splitlines()
        if not line.lstrip().startswith(("//", "*", "/*"))
    ]
    lines_with_bare_api = [
        line for line in code_lines
        if ("'/_api/" in line or "`/_api/" in line) and "apiUrl" not in line
    ]
    assert lines_with_bare_api == [], (
        "Found bare '/_api/' URL literals in code (which target the root "
        "web on sub-sites). Use apiUrl(suffix) instead. Offending lines:\n"
        + "\n".join(lines_with_bare_api)
    )


def test_tojson_escapes_injection_chars(tmp_path: Path) -> None:
    """A5: schema-controlled strings (a field description) are emitted through
    tojson htmlsafe escaping, so <, >, & and </script> are unicode-escaped and
    cannot break out of the generated JS. Locks the invariant against a future
    refactor reintroducing a raw interpolation."""
    from dbml_sharepoint.model.mapping_loader import load_mapping

    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Widget {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar [not null]\n"
        "  Field1 nvarchar [note: 'Bad </script><tag> and & value']\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Widget: { kind: List, base_template: 100, site_role: default }\n",
        encoding="utf-8",
    )
    schema = parse_dbml(tmp_path / "s.dbml")
    bundle = load_mapping(tmp_path / "m.yaml")
    release = load_release(FIXTURES / "release.yaml")
    js = generate_deploy_js(
        schema=schema, bundle=bundle, release=release,
        site_url="https://example.sharepoint.com/sites/t", site_role="default",
        source_dbml="s.dbml", source_mtime="2026-05-04T00:00:00Z",
        generated_at="2026-05-04T00:00:00Z",
    )
    assert "</script>" not in js  # literal breakout sequence absent
    assert "\\u003c/script\\u003e" in js  # tojson htmlsafe escaped it
    assert "\\u0026" in js  # & escaped


def test_generated_js_aborts_when_sp_page_context_missing() -> None:
    """The deploy script depends on _spPageContextInfo for both the
    site-mismatch preflight and the WEB url prefix. If it's absent we
    must abort cleanly rather than silently routing API calls to the
    tenant root."""
    js = _generate_simple_js()
    assert "typeof _spPageContextInfo === 'undefined'" in js
    assert "no-sp-page-context" in js


def test_schema_json_has_permission_keys() -> None:
    """SCHEMA literal in generated JS must include permission_levels, groups,
    list_assignments keys (R5)."""
    from dbml_sharepoint.generators.jsgen import build_schema_json
    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    schema_json = build_schema_json(schema, bundle, "default")

    assert "permission_levels" in schema_json
    assert "groups" in schema_json
    assert "list_assignments" in schema_json

    # Fixture has one custom level and one group.
    assert len(schema_json["permission_levels"]) == 1
    assert schema_json["permission_levels"][0]["name"] == "Schema Manager"
    assert "high" in schema_json["permission_levels"][0]["base_permissions"]
    assert "low" in schema_json["permission_levels"][0]["base_permissions"]

    assert len(schema_json["groups"]) == 1
    assert schema_json["groups"][0]["name"] == "List Maintainer"
    assert schema_json["groups"][0]["require_empty_at_deploy"] is True

    # All default-role lists should have assignments.
    assert len(schema_json["list_assignments"]) == 3
    assert all(
        item["reconcile_mode"] == "exact"
        for item in schema_json["list_assignments"]
    )
    list_names = {la["list"] for la in schema_json["list_assignments"]}
    assert "APP_Project" in list_names
    assert "APP_Task" in list_names
    assert "APP_AppSettings" in list_names


def test_deploy_js_phase1_reliability_hardening() -> None:
    """A4: the generated deploy.js must (a) carry a Retry-After-aware retry
    helper, (b) refresh the request digest inside the Phase 2.1 list loop, (c)
    guard each Phase 2.1 field POST in its own try/catch, and (d) reconcile stale
    role bindings in Phase 4.2 (remove-before-add)."""
    js = _generate_simple_js()
    # (a) retry helper honouring Retry-After
    assert "fetchWithRetry" in js
    assert "Retry-After" in js
    # (b) per-list digest refresh: getDigest() must be called inside the
    # Phase 2.1 `for (const list of SCHEMA.lists)` loop, not only once before it.
    phase1 = js.split(f"Starting Phase {pn('lists')}")[1].split(
        f"Starting Phase {pn('lookups')}")[0]
    assert "for (const list of SCHEMA.lists)" in phase1
    assert "digest = await getDigest()" in phase1
    # (c) per-field guard marker
    assert f"Phase {pn('lists')} field" in js
    # (d) Phase 4.2 reconcile
    assert "getbyprincipalid" in js
    assert "removeroleassignment" in js


def test_existing_schema_shape_preflight_is_fail_closed() -> None:
    """Same-name lists/fields are not accepted as idempotency evidence."""
    js = _generate_simple_js()

    assert f"Starting Phase {pn('preflight')}: read-only preflight" in js
    assert "$select=${select}" in js
    assert "BaseTemplate" in js
    assert "ContentTypesEnabled" in js
    assert "EnableVersioning" in js
    assert "EnableMinorVersions" in js
    assert "MajorVersionLimit" in js
    assert "SharePoint list/library templates are immutable" in js
    assert "getbyinternalnameortitle" in js
    assert "TypeAsString" in js
    assert "EnforceUniqueValues" in js
    assert "ReadOnlyField" in js
    assert "Sealed" in js
    assert "DefaultValue" in js
    assert "derived-shape probe" in js
    for property_name in (
        "MaxLength",
        "RichText",
        "NumberOfLines",
        "AppendOnly",
        "Choices",
        "FillInChoice",
        "DisplayFormat",
        "SelectionMode",
    ):
        assert property_name in js
    assert "existing-schema-shape-errors" in js
    assert "no deployment writes were attempted" in js
    assert js.index(f"Starting Phase {pn('preflight')}: read-only preflight") < js.index(
        f"Starting Phase {pn('security')}",
    )
    assert js.index("existing-schema-shape-errors") < js.index(f"Starting Phase {pn('security')}")


def test_existing_lookup_shape_requires_exact_target_and_display_field() -> None:
    """An existing lookup cannot silently retain another list/field target."""
    js = _generate_simple_js()

    assert "?$select=LookupList,LookupField" in js
    assert "normalizeGuid(actual.LookupList)" in js
    assert "expectedLookupFieldInternalName" in js
    assert "actual.LookupField !== expectedLookupField" in js
    assert "Lookup targets are immutable" in js
    assert "declared target list" in js


def test_mutable_list_and_field_shape_is_reconciled_and_read_back() -> None:
    """Only declared mutable properties are MERGEd after immutable checks."""
    js = _generate_simple_js()

    assert "assertListImmutableShape(list, actual)" in js
    assert "await patchList" in js
    assert "did not retain declared setting(s)" in js
    assert "await assertFieldImmutableShape" in js
    assert "patchBody.Description = desired.description" in js
    assert "patchBody.Required = desired.required" in js
    assert "patchBody.EnforceUniqueValues = desired.enforceUniqueValues" in js
    assert "patchBody.Indexed = desired.indexed" in js
    assert "patchBody.DefaultValue = desired.defaultValue" in js
    assert "sameDerivedValue" in js
    assert "patchBody[name] = value" in js
    assert "fields/getbyinternalnameortitle('${odataName(columnName)}')" in js
    assert "fields/getbytitle('${odataName(columnName)}')" not in js
    assert "is sealed; expected an unsealed declared field" in js
    assert "DefaultValue readback did not match" in js
    assert "Send only drifted writable properties" in js
    assert "did not retain declared mutable setting(s)" in js
    assert js.index("await assertFieldImmutableShape") < js.index(
        "await patchField(listName, field.title",
    )
    assert "phase-1-schema-errors" in js
    assert "phase-2-schema-errors" in js
    assert js.index("phase-1-schema-errors") < js.index(f"Starting Phase {pn('lookups')}")
    assert js.index("phase-2-schema-errors") < js.index(f"Starting Phase {pn('indexes')}")


def test_choice_fields_disable_fill_in_and_preserve_exact_order() -> None:
    """Choice adoption cannot silently accept extra/reordered free-form values."""
    from dbml_sharepoint.generators.jsgen import build_schema_json

    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    schema_json = build_schema_json(schema, bundle, "default")
    project = next(lst for lst in schema_json["lists"] if lst["title"] == "APP_Project")
    status = next(field for field in project["fields_phase1"] if field["title"] == "Status")

    assert status["body"]["Choices"] == {"results": ["Open", "Closed"]}
    assert status["body"]["FillInChoice"] is False


def test_exact_acl_reconciliation_removes_unlisted_principals() -> None:
    """Exact mode is a real allowlist, not just stale-level cleanup for the
    principals that happen to be declared in the mapping."""
    js = _generate_simple_js()
    assert "reconcile_mode" in js
    assert "roleassignments?$expand=Member,RoleDefinitionBindings" in js
    assert "const expected = new Set" in js
    assert "removeBinding(principalId, binding.Id, 'unlisted')" in js
    assert "binding.Name === 'Limited Access'" in js
    assert "while (assignmentsUrl)" in js
    assert "allJson.d.__next" in js
    assert "cannot resolve desired assignment" in js
    assert js.index("addroleassignment") < js.index(
        "Exact mode treats the mapping as an allowlist",
    )
    assert "failed before reconciliation" in js
    assert "desiredPresent" in js


def test_role_assignment_reads_use_positional_getbyprincipalid() -> None:
    """SharePoint's REST read method is positional; add/remove remain named."""
    js = _generate_simple_js()

    positional = "getbyprincipalid(${resolved.principalId})"
    assert js.count(positional) == 2
    assert "getbyprincipalid(principalid=" not in js
    assert "addroleassignment(principalid=${resolved.principalId}" in js
    assert "removeroleassignment(principalid=${principalId}" in js


def test_no_title_list_gets_required_false_title_patch(tmp_path: Path) -> None:
    """A4: a list with no DBML Title column gets its built-in Title patched
    Required:false so programmatic inserts / manual entry aren't blocked."""
    from dbml_sharepoint.generators.jsgen import build_schema_json
    from dbml_sharepoint.model.mapping_loader import load_mapping

    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Attendance {\n"
        "  Id int [pk, increment]\n"
        "  Notes nvarchar\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Attendance: { kind: List, base_template: 100, site_role: default }\n",
        encoding="utf-8",
    )
    schema = parse_dbml(tmp_path / "s.dbml")
    bundle = load_mapping(tmp_path / "m.yaml")
    sj = build_schema_json(schema, bundle, "default")
    att = next(lst for lst in sj["lists"] if lst["title"] == "APP_Attendance")
    assert att["title_patch"] is not None
    assert att["title_patch"]["Required"] is False


def test_generated_js_contains_phase_0_and_phase_4() -> None:
    """deploy.js must include Phase 1.2 (level/group creation) and Phase 4.2
    (break inheritance + role assignments) markers and SP REST calls (R6)."""
    js = _generate_simple_js()

    assert f"Phase {pn('security')}" in js
    assert f"Phase {pn('acls')}" in js
    assert "breakroleinheritance" in js
    assert "addroleassignment" in js


# === New tests for Feature A (owner verification) and Feature B (Phase 5.1 seed) ===


def test_deploy_js_hardens_permission_and_role_checks() -> None:
    """Template hardening guards:
    - permission preflight demands ManagePermissions only when the schema has
      ACL work (needsPermissions), not unconditionally;
    - Phase 1.2 role-definition / site-group existence probes surface non-404
      responses as errors rather than treating them as "already exists";
    - Phase 4.2 addroleassignment / breakroleinheritance and the Phase 1.2 group
      owner reads all validate the HTTP result (fetch does not throw on 4xx/5xx).
    """
    js = _generate_simple_js()
    assert "needsPermissions" in js
    assert "Probe for permission level" in js
    assert "Probe for site group" in js
    assert "addroleassignment (principal" in js
    assert "failed before reconciliation" in js
    assert "breakroleinheritance failed" in js
    assert "/owner?$select=Id,Title,PrincipalType" in js
    assert "Cannot read owner for group" in js


def test_group_owner_is_verified_read_only_and_mismatch_fails_closed() -> None:
    """Never write read-only OwnerTitle or guess a REST Owner POST payload."""
    js = _generate_simple_js()

    assert "Manual owner action required for group" in js
    assert f"Phase {pn('lists')} will not start while this mismatch exists" in js
    assert "owner verified as" in js
    assert "OwnerTitle:" not in js
    assert "owner MERGE failed" not in js
    assert js.index("Manual owner action required for group") < js.index(
        "phase-0-security-errors",
    )


def test_deploy_js_reconciles_named_security_objects_and_fails_closed() -> None:
    """A matching name is not sufficient security evidence.

    Existing custom role definitions and groups must have their declared
    permissions/membership controls reconciled. Any Phase 1.2 failure must stop
    before list creation, and any later schema/ACL failure must stop before a
    seed row can make a partial deployment appear activated.
    """
    js = _generate_simple_js()

    assert "Permission level '${lvl.name}' MERGE failed" in js
    assert "declared permissions reconciled" in js
    assert "Group '${grp.name}' settings MERGE failed" in js
    assert "declared membership controls reconciled" in js
    assert "phase-0-security-errors" in js
    assert js.index("phase-0-security-errors") < js.index(f"Starting Phase {pn('lists')}")
    assert "pre-seed-errors" in js
    assert js.index("pre-seed-errors") < js.index(f"Starting Phase {pn('seeds')}")


def test_required_empty_group_is_paginated_and_fails_before_phase_1() -> None:
    """The optional bootstrap gate observes membership without mutating it."""
    js = _generate_simple_js()

    assert '"require_empty_at_deploy": true' in js
    assert "/users?$select=Id&$top=5000" in js
    assert "while (membersUrl)" in js
    assert "membersJson.d.__next" in js
    assert "requires empty membership at deploy" in js
    assert "membership enumeration failed" in js
    assert "is empty as required for deployment" in js
    assert js.index("const currentOwner =") < js.index(
        "if (grp.require_empty_at_deploy)",
    )
    assert js.index("while (membersUrl)") < js.index("phase-0-security-errors")
    assert js.index("phase-0-security-errors") < js.index(f"Starting Phase {pn('lists')}")
    # The gate itself observes without mutating: no member removal between
    # the gate's guard and its success log. (Member removal DOES exist
    # elsewhere in the script — the run-scoped operator self-enrolment
    # cleanup — which never touches pre-existing members.)
    gate_block = js[
        js.index("if (grp.require_empty_at_deploy)"):js.index("is empty as required for deployment")
    ]
    assert "/users/removebyid" not in gate_block
    assert "/users/removebyloginname" not in js
    assert js.count("/users/removebyid(") == 1  # only the self-enrolment cleanup
    assert js.index("removeSelfEnrollments") < js.index("/users/removebyid(")


def test_exact_lists_break_inheritance_immediately_in_phase_1() -> None:
    """Exact-mode lists must not inherit Team rights until the ACL phase."""
    js = _generate_simple_js()
    phase1 = js.split(f"Starting Phase {pn('lists')}")[1].split(
        f"Starting Phase {pn('lookups')}")[0]

    assert "earlyIsolationLists" in phase1
    assert "la.break_inheritance && la.reconcile_mode === 'exact'" in phase1
    assert "early HasUniqueRoleAssignments probe failed" in phase1
    assert "early breakroleinheritance failed" in phase1
    break_call = (
        "breakroleinheritance(copyRoleAssignments=false,clearSubscopes=false)"
    )
    assert break_call in phase1
    assert js.count(break_call) == 2  # early isolation plus full Phase 4.2 guard
    assert "clearSubscopes=true" not in phase1
    assert phase1.index("listGuids[list.title] = listShape.Id") < phase1.index(
        "if (earlyIsolationLists.has(list.title))",
    ) < phase1.index("for (const col of list.fields_phase1)")


def test_new_exact_list_must_remain_empty_after_early_isolation() -> None:
    """A row raced into the create/break gap must block fields and seeding."""
    js = _generate_simple_js()
    phase1 = js.split(f"Starting Phase {pn('lists')}")[1].split(
        f"Starting Phase {pn('lookups')}")[0]

    assert "let createdThisRun = false" in phase1
    assert "createdThisRun = true" in phase1
    assert "$select=ItemCount" in phase1
    assert "post-isolation ItemCount probe failed" in phase1
    assert "post-isolation ItemCount probe returned an invalid response" in phase1
    assert "contains ${itemCount} item(s) after early isolation" in phase1
    assert "remains empty after early isolation" in phase1
    assert "summary.errors.push({ phase: '2.1'" in phase1
    assert phase1.index("early breakroleinheritance failed") < phase1.index(
        "$select=ItemCount",
    ) < phase1.index("for (const col of list.fields_phase1)")
    assert js.index("contains ${itemCount} item(s) after early isolation") < js.index(
        "pre-seed-errors",
    )


def test_singleton_seed_existing_row_must_match_exactly() -> None:
    """Seed idempotency verifies the singleton; it never trusts any row."""
    js = _generate_simple_js()
    phase5 = js.split(f"Starting Phase {pn('seeds')}")[1]

    assert "exactSeedValueEqual" in phase5
    assert "actual === null && expected === ''" in phase5
    assert "do not coerce any other scalar values" in phase5
    assert "key !== '__metadata'" in phase5
    assert "readSeedSingleton" in phase5
    assert "?$top=2&$select=${selectFields}" in phase5
    assert "Object.prototype.hasOwnProperty.call(existing, field)" in phase5
    assert "does not exactly match declared field(s)" in phase5
    assert "contains multiple rows" in phase5
    assert "Verified existing singleton row" in phase5
    assert "Seeded and verified" in phase5
    assert "phase-5-seed-errors" in phase5
    assert "deployment is not activation-ready" in phase5
    assert phase5.count("await readSeedSingleton(seed)") == 2
    assert "already has a row, skipping seed" not in phase5
    assert "not present (HTTP" not in phase5


def test_exact_acl_reconciliation_detects_descendant_unique_scopes() -> None:
    """Exact list ACLs must not conceal stale item/folder permission scopes.

    The deployer enumerates all items (including document-library folders/files)
    before any break/reconciliation, follows paging, uses
    clearSubscopes=false, and fails closed for explicit operator review.
    """
    js = _generate_simple_js()

    assert "$select=Id,HasUniqueRoleAssignments&$top=5000" in js
    assert "while (itemsUrl)" in js
    assert "itemsJson.d.__next" in js
    assert "item/folder unique permission scope(s) remain" in js
    assert "never erase" in js
    assert (
        "breakroleinheritance(copyRoleAssignments=false,clearSubscopes=false)" in js
    )
    assert (
        "breakroleinheritance(copyRoleAssignments=false,clearSubscopes=true)" not in js
    )
    descendant_probe = "await findDescendantUniqueScopeIds(la.list)"
    assert js.count(descendant_probe) == 2
    break_call = "breakroleinheritance(copyRoleAssignments=false,clearSubscopes=false)"
    phase4 = js.split(f"Starting Phase {pn('acls')}")[1].split(f"Starting Phase {pn('seeds')}")[0]
    assert phase4.index(descendant_probe) < phase4.index(break_call)


def test_other_role_build_does_not_apply_scoped_default_policy() -> None:
    """Regression: with a role-scoped default policy, a build for another role
    must emit NO list_assignments for that role's lists (previously the default fell
    back onto every entity, re-ACLing them with the other role's groups)."""
    from dbml_sharepoint.generators.jsgen import build_schema_json
    from dbml_sharepoint.model.mapping_loader import EntityMapping

    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    assert bundle.mapping.permissions is not None
    assert bundle.mapping.permissions.default_policy_site_role == "default"
    bundle.mapping.entities["Task"] = EntityMapping(
        name="Task", kind="HubOnlyList", base_template=100, site_role="admin",
    )

    hub_json = build_schema_json(schema, bundle, "admin")
    assert [lst["title"] for lst in hub_json["lists"]] == ["APP_Task"]
    assert hub_json["list_assignments"] == []

    default_json = build_schema_json(schema, bundle, "default")
    assert {la["list"] for la in default_json["list_assignments"]} == {
        "APP_Project", "APP_AppSettings",
    }


def test_seed_items_empty_with_null_extension() -> None:
    """With no extension (NullExtension default), the schema
    view exposes an empty ``seed_items`` list and carries NO organisation-specific
    keys — seeding belongs to extensions."""
    from dbml_sharepoint.generators.jsgen import build_schema_json

    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")

    sj = build_schema_json(schema, bundle, "default")

    assert sj["seed_items"] == []
    assert "app_settings_seed" not in sj


class _SeedExtension(BaseExtension):
    """Stub extension that seeds one list item into a titled list."""

    name: ClassVar[str] = "seedstub"

    def seed_lists(
        self, bundle: Any, schema: Any, site_context: SiteContext,
    ) -> dict[str, dict[str, Any]]:
        return {
            "APP_AppSettings": {
                "Title": "App Settings",
                "UnitName": "Zeta Unit",
            },
        }


def test_stub_extension_seed_rendered_in_generic_phase_5() -> None:
    """An extension's ``seed_lists`` entry ({title: fields}) surfaces as a
    ``seed_items`` element and drives the generic Phase 5.1 loop: the rendered
    deploy.js contains the list title, the field payload, and fetches
    ``ListItemEntityTypeFullName`` (no hardcoded ``SP.Data.*`` literal)."""
    from dbml_sharepoint.generators.jsgen import build_schema_json

    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    release = load_release(FIXTURES / "release.yaml")

    sj = build_schema_json(
        schema, bundle, "default",
        site_url="https://example.sharepoint.com/sites/t1",
        release=release,
        extension=_SeedExtension(),
    )
    assert sj["seed_items"] == [
        {
            "title": "APP_AppSettings",
            "fields": {
                "Title": "App Settings",
                "UnitName": "Zeta Unit",
            },
            "skip_if_has_rows": True,
        },
    ]

    js = generate_deploy_js(
        schema=schema,
        bundle=bundle,
        release=release,
        site_url="https://example.sharepoint.com/sites/t1",
        site_role="default",
        source_dbml="simple.dbml",
        source_mtime="2026-05-04T00:00:00Z",
        generated_at="2026-05-04T00:00:00Z",
        extension=_SeedExtension(),
    )
    assert f"Phase {pn('seeds')}" in js
    assert "SCHEMA.seed_items" in js
    assert "ListItemEntityTypeFullName" in js
    assert "readSeedSingleton" in js
    assert "assertSeedSingletonMatches" in js
    assert "APP_AppSettings" in js
    assert "Zeta Unit" in js
    # The old hardcoded item type literal must be gone.
    assert "SP.Data.APP_AppSettingsListItem" not in js


def test_cross_site_column_without_extension_is_error_finding() -> None:
    """A column declared in ``cross_site_reference_columns`` requires an
    extension whose ``expand_column`` handles it. With NullExtension
    (expand_column returns None), validate_all must surface an error
    Finding rather than silently emitting an unexpanded column."""
    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    bundle.mapping.cross_site_reference_columns.append(
        CrossSiteRef(entity="Task", column="Project"),
    )

    findings = validate_all(schema, bundle, NullExtension())

    assert any(
        f.severity == "error" and "expand_column" in f.message for f in findings
    )


def test_calculated_field_rendered_with_formula_and_output_type() -> None:
    """calculated_* columns render as SP.FieldCalculated with the mapping's
    formula and the right OutputType; they are never marked Required."""
    schema = parse_dbml(FIXTURES / "calculated.dbml")
    bundle = load_mapping(FIXTURES / "calculated-mapping.yaml")
    release = load_release(FIXTURES / "release.yaml")
    js = generate_deploy_js(
        schema=schema, bundle=bundle, release=release,
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default",
        source_dbml="calculated.dbml",
        source_mtime="2026-05-04T00:00:00Z",
        generated_at="2026-05-04T00:00:00Z",
    )
    assert "SP.FieldCalculated" in js
    assert '"FieldTypeKind": 17' in js
    assert '"OutputType": 9' in js   # RiskScore -> Number
    assert '"OutputType": 2' in js   # RiskBand -> Text
    assert "IF([Severity]=" in js    # the formula body made it through


def test_calculated_fields_are_created_after_referenced_columns(
    tmp_path: Path,
) -> None:
    """SharePoint validates a calculated formula's [Column] references when
    the field is CREATED, so a calculated field POSTed before a column its
    formula references fails with HTTP 500 ("The formula refers to a column
    that does not exist"). Seen live on a register pack: the
    MatrixVersion guard column was declared after the two matrix formulas
    that reference it. Phase-1 field order must keep plain fields in
    declaration order (which drives form order; calculated fields never
    appear on entry forms) and move calculated fields after them,
    topologically ordered among themselves for calc-on-calc chains."""
    from dbml_sharepoint.generators.jsgen import build_schema_json

    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Enum severity {\n"
        '  "Low"\n'
        '  "High"\n'
        "}\n"
        "Table Risk {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar [not null]\n"
        "  Severity severity\n"
        "  Score calculated_number\n"
        "  Rating calculated_text\n"
        "  MatrixVersion nvarchar\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Risk: { kind: List, base_template: 100, site_role: default }\n"
        "calculated_formulas:\n"
        "  Risk:\n"
        # Score depends on Rating (calc-on-calc) although declared first;
        # Rating depends on the plain columns declared AFTER both.
        "    Score: '=IF([Rating]=\"High\",10,1)'\n"
        "    Rating: '=IF([MatrixVersion]=\"13.0\",[Severity],\"\")'\n",
        encoding="utf-8",
    )
    schema = parse_dbml(tmp_path / "s.dbml")
    bundle = load_mapping(tmp_path / "m.yaml")
    risk = next(
        lst for lst in build_schema_json(schema, bundle, "default")["lists"]
        if lst["title"] == "APP_Risk"
    )
    assert [field["title"] for field in risk["fields_phase1"]] == [
        "Severity", "MatrixVersion", "Rating", "Score",
    ]


def test_calculated_field_shape_gate_expects_intrinsic_read_only() -> None:
    """SP.FieldCalculated is intrinsically ReadOnlyField=true (users never
    write it), so a blanket writability assertion rejects every calculated
    field the deployer itself created a moment earlier — the rerun/resume
    path fails in preflight with 'read-only or sealed; expected a writable
    declared field'. The shape gate must expect read-only exactly for
    declared calculated fields, still reject read-only for every other
    declared type, and treat sealed as fatal for all."""
    schema = parse_dbml(FIXTURES / "calculated.dbml")
    bundle = load_mapping(FIXTURES / "calculated-mapping.yaml")
    release = load_release(FIXTURES / "release.yaml")
    js = generate_deploy_js(
        schema=schema, bundle=bundle, release=release,
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default",
        source_dbml="calculated.dbml",
        source_mtime="2026-05-04T00:00:00Z",
        generated_at="2026-05-04T00:00:00Z",
    )
    assert "const expectReadOnly = desired.typeAsString === 'Calculated'" in js
    assert "actual.ReadOnlyField !== expectReadOnly" in js
    assert "is sealed; expected an unsealed declared field" in js
    assert "expected a writable declared field" not in js


def test_formula_comparison_decodes_xml_character_entities() -> None:
    """SharePoint stores a calculated field's Formula in the field schema XML
    and returns it with XML character entities intact (a formula containing
    `<>` reads back as `&lt;&gt;`), so a byte-for-byte comparison never
    converges: reconciliation MERGEs the identical formula and the readback
    'drift' persists — 'did not retain declared mutable setting(s): Formula'
    on every rerun. Formula comparison must canonicalise both sides by
    decoding XML entities (amp last, so double-encoded text stays distinct)."""
    schema = parse_dbml(FIXTURES / "calculated.dbml")
    bundle = load_mapping(FIXTURES / "calculated-mapping.yaml")
    release = load_release(FIXTURES / "release.yaml")
    js = generate_deploy_js(
        schema=schema, bundle=bundle, release=release,
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default",
        source_dbml="calculated.dbml",
        source_mtime="2026-05-04T00:00:00Z",
        generated_at="2026-05-04T00:00:00Z",
    )
    assert "if (name === 'Formula') return canonicalFormula(value)" in js
    assert "replace(/&lt;/g, '<')" in js
    assert "replace(/&gt;/g, '>')" in js
    assert "replace(/&quot;/g, '\"')" in js
    assert "replace(/&amp;/g, '&')" in js
    assert js.index("replace(/&lt;/g") < js.index("replace(/&amp;/g")


def test_formula_comparison_strips_removable_reference_brackets() -> None:
    """SharePoint canonicalises a stored formula's column references: square
    brackets around names that do not need delimiting are stripped
    (`[Likelihood]` is stored and read back as `Likelihood`), so a
    byte-for-byte comparison of declared vs readback never converges even
    after XML entity decoding — the same trap the PnP provisioning engine
    documents. The comparison must canonicalise both sides by removing
    removable brackets OUTSIDE string literals only: bracket text inside a
    quoted constant is data, not a reference."""
    js = _generate_simple_js()
    probe = js.split("const canonicalFormula")[1].split("function normalizeDerivedValue")[0]
    assert 'split(/("(?:""|[^"])*")/)' in probe
    assert "replace(/\\[([A-Za-z0-9_]+)\\]/g, '$1')" in probe
    assert "i % 2 === 1 ? token" in probe  # string-literal tokens pass through


def test_mutable_drift_errors_carry_declared_and_readback_values() -> None:
    """A drift that survives reconciliation must be diagnosable from the
    console log alone: the error names each setting WITH the declared and
    readback values, not just the property name (live debugging of a register
    formula loop burned three paste round-trips on 'Formula' with no
    values)."""
    js = _generate_simple_js()
    assert "const drift = (name, declaredValue, actualValue)" in js
    assert "declared ${JSON.stringify(declaredValue)}" in js
    assert "readback ${JSON.stringify(actualValue)}" in js
    assert "did not retain declared mutable setting(s)" in js


def test_calculated_kind_wired_into_reconciliation_machinery() -> None:
    """FieldTypeKind 17 must be declared in TYPE_AS_STRING_BY_KIND and
    Formula/OutputType must be probed + reconciled derived properties.
    Without them declaredFieldState throws immediately after Phase 2.1 creates
    a calculated field, aborting the whole deployment."""
    schema = parse_dbml(FIXTURES / "calculated.dbml")
    bundle = load_mapping(FIXTURES / "calculated-mapping.yaml")
    release = load_release(FIXTURES / "release.yaml")
    js = generate_deploy_js(
        schema=schema, bundle=bundle, release=release,
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default",
        source_dbml="calculated.dbml",
        source_mtime="2026-05-04T00:00:00Z",
        generated_at="2026-05-04T00:00:00Z",
    )
    assert "[17, 'Calculated']" in js
    # Once in readFieldShape's probe list, once in DERIVED_FIELD_PROPERTIES.
    assert js.count("'Formula', 'OutputType'") >= 2


def test_permission_level_probe_uses_filter_not_getbyname() -> None:
    """SP's roledefinitions/getbyname returns HTTP 500 (not 404) for a missing
    role definition, so a getbyname existence probe fails Phase 1.2 on every
    clean site (first real-tenant paste). The probe must use the $filter form,
    which returns 200 + empty results when absent; getbyname remains only on
    the MERGE path for an existing level."""
    js = _generate_simple_js()
    assert "web/roledefinitions?$select=Id&$filter=Name eq" in js


def test_field_probe_treats_missing_column_400_as_absent() -> None:
    """SP's fields/getbyinternalnameortitle returns HTTP 400
    (System.ArgumentException, locale-invariant code -2147024809, "Column 'X'
    does not exist") for a missing field — not 404 like the list/group
    getters. Treating only 404 as absent aborted every clean first provision
    in Phase 2.1: each just-created list's declared fields all failed their
    shape probe before they could be created. The probe must map exactly that
    400 shape to "field absent" (the create path) and keep every other
    non-ok response fatal."""
    js = _generate_simple_js()
    helper = js.split("const isAbsent400")[1].split("async function")[0]
    assert "-2147024809" in helper
    assert "System.ArgumentException" in helper
    field_probe = js.split("async function readFieldShape")[1].split("async function")[0]
    assert "isAbsent400(r.status, text)" in field_probe
    assert "return null" in field_probe
    # The narrow match must not relax the fatal path for other errors.
    assert "shape probe failed" in field_probe


def test_group_management_automation_rendered(tmp_path: Path) -> None:
    """The generated script must carry (a) the CSOM ProcessQuery owner-set
    fallback for mismatched group owners and (b) the operator self-enrolment
    machinery keyed by groups[].enroll_operator_during_deploy."""
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
    js = generate_deploy_js(
        schema=schema, bundle=bundle, release=release,
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default",
        source_dbml="calculated.dbml",
        source_mtime="2026-05-04T00:00:00Z",
        generated_at="2026-05-04T00:00:00Z",
    )
    assert '"enroll_operator_during_deploy": true' in js
    assert "ProcessQuery" in js          # owner-set fallback endpoint
    assert "SetProperty" in js           # CSOM payload
    assert "removeSelfEnrollments" in js # end-of-run cleanup helper


# --- Declared views ---------------------------------------------------------


def _caml(view_kwargs: dict[str, Any], column_types: dict[str, str] | None = None) -> str:
    from dbml_sharepoint.generators.jsgen import _view_caml_query
    from dbml_sharepoint.model.mapping_loader import ViewDef

    return _view_caml_query(
        ViewDef(title="V", fields=["Title"], **view_kwargs),
        column_types or {},
    )


def test_view_caml_condition_sort_and_group() -> None:
    from dbml_sharepoint.model.conditions import parse_condition
    from dbml_sharepoint.model.mapping_loader import ViewGroupBy, ViewSort

    caml = _caml(
        dict(
            where=parse_condition([{"field": "Status", "op": "neq", "value": "Closed"}], "w"),
            sort=[ViewSort(field="RiskScore", direction="desc")],
            group_by=ViewGroupBy(field="Impact", collapsed=True),
        ),
        {"Status": "status_enum", "RiskScore": "calculated_number", "Impact": "impact_enum"},
    )
    assert caml == (
        '<GroupBy Collapse="TRUE"><FieldRef Name="Impact"/></GroupBy>'
        '<Where><Neq><FieldRef Name="Status"/>'
        '<Value Type="Text">Closed</Value></Neq></Where>'
        '<OrderBy><FieldRef Name="RiskScore" Ascending="FALSE"/></OrderBy>'
    )


def test_view_caml_ands_multiple_conditions() -> None:
    from dbml_sharepoint.model.conditions import parse_condition

    caml = _caml(
        dict(where=parse_condition(
            [
                {"field": "Status", "op": "eq", "value": "Open"},
                {"field": "SortOrder", "op": "geq", "value": 5},
                {"field": "Owner", "op": "is_not_null"},
            ],
            "w",
        )),
        {"Status": "status_enum", "SortOrder": "int", "Owner": "person"},
    )
    assert caml == (
        "<Where><And><And>"
        '<Eq><FieldRef Name="Status"/><Value Type="Text">Open</Value></Eq>'
        '<Geq><FieldRef Name="SortOrder"/><Value Type="Number">5</Value></Geq>'
        "</And>"
        '<IsNotNull><FieldRef Name="Owner"/></IsNotNull>'
        "</And></Where>"
    )


def test_view_caml_today_offsets_and_ascending_sort() -> None:
    from dbml_sharepoint.model.conditions import parse_condition
    from dbml_sharepoint.model.mapping_loader import ViewSort

    caml = _caml(
        dict(
            where=parse_condition([{"field": "DueDate", "op": "leq", "value": "today+30"}], "w"),
            sort=[ViewSort(field="DueDate", direction="asc")],
        ),
        {"DueDate": "date"},
    )
    assert caml == (
        '<Where><Leq><FieldRef Name="DueDate"/>'
        '<Value Type="DateTime"><Today OffsetDays="30"/></Value></Leq></Where>'
        '<OrderBy><FieldRef Name="DueDate"/></OrderBy>'
    )
    bare = _caml(
        dict(where=parse_condition([{"field": "DueDate", "op": "eq", "value": "today"}], "w")),
        {"DueDate": "datetime"},
    )
    assert '<Value Type="DateTime"><Today/></Value>' in bare
    minus = _caml(
        dict(where=parse_condition([{"field": "DueDate", "op": "gt", "value": "today-7"}], "w")),
        {"DueDate": "date"},
    )
    assert '<Today OffsetDays="-7"/>' in minus


def test_view_caml_escapes_values_and_maps_boolean() -> None:
    from dbml_sharepoint.model.conditions import parse_condition

    caml = _caml(
        dict(where=parse_condition([{"field": "Name", "op": "eq", "value": 'A & B < "C"'}], "w")),
        {"Name": "nvarchar"},
    )
    assert '<Value Type="Text">A &amp; B &lt; &quot;C&quot;</Value>' in caml
    flag = _caml(
        dict(where=parse_condition([{"field": "Active", "op": "eq", "value": True}], "w")),
        {"Active": "boolean"},
    )
    assert '<Value Type="Integer">1</Value>' in flag


def test_schema_json_carries_declared_views(tmp_path: Path) -> None:
    from dbml_sharepoint.generators.jsgen import build_schema_json

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
        "        - { field: DueDate, direction: asc }\n"
        "      row_limit: 100\n",
        encoding="utf-8",
    )
    schema = parse_dbml(tmp_path / "s.dbml")
    bundle = load_mapping(tmp_path / "m.yaml")
    schema_json = build_schema_json(schema, bundle, "default")
    assert schema_json["views"] == [{
        "list": "APP_Risk",
        "title": "Open risks",
        "view_fields": ["Title", "Status", "DueDate"],
        "caml_query": (
            '<Where><Neq><FieldRef Name="Status"/>'
            '<Value Type="Text">Closed</Value></Neq></Where>'
            '<OrderBy><FieldRef Name="DueDate"/></OrderBy>'
        ),
        "row_limit": 100,
        "set_default": True,
        "formatting": None,
        "widths": None,
        "url_slug": "OpenRisks",
    }]


def test_view_widths_emitted_by_display_name(tmp_path: Path) -> None:
    """ColumnWidth FieldRefs bind by DISPLAY title (live finding: internal
    names are accepted but silently reset widths), so the generator rewrites
    widths keys with display_name_for — the same generation-time rewrite
    calculated formulas and form bodies use."""
    from dbml_sharepoint.generators.jsgen import build_schema_json

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
        "display_names:\n"
        "  mode: auto\n"
        "views:\n"
        "  Risk:\n"
        "    - title: Sized\n"
        "      fields: [Title, DueDate]\n"
        "      widths:\n"
        "        Title: 240\n"
        "        DueDate: 150\n",
        encoding="utf-8",
    )
    schema = parse_dbml(tmp_path / "s.dbml")
    bundle = load_mapping(tmp_path / "m.yaml")
    schema_json = build_schema_json(schema, bundle, "default")
    assert schema_json["views"][0]["widths"] == {"Title": 240, "Due Date": 150}


def test_schema_json_views_empty_without_declarations() -> None:
    from dbml_sharepoint.generators.jsgen import build_schema_json

    schema = parse_dbml(FIXTURES / "calculated.dbml")
    bundle = load_mapping(FIXTURES / "calculated-mapping.yaml")
    assert build_schema_json(schema, bundle, "default")["views"] == []


def _generate_views_js(tmp_path: Path) -> str:
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
    return generate_deploy_js(
        schema=parse_dbml(tmp_path / "s.dbml"),
        bundle=load_mapping(tmp_path / "m.yaml"),
        release=load_release(FIXTURES / "release.yaml"),
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default",
        source_dbml="s.dbml",
        source_mtime="2026-05-04T00:00:00Z",
        generated_at="2026-05-04T00:00:00Z",
    )


def test_view_probe_treats_missing_view_400_as_absent(tmp_path: Path) -> None:
    """views/getbytitle signals a missing view the same way
    fields/getbyinternalnameortitle signals a missing field: HTTP 400
    System.ArgumentException ("The specified view is invalid."), code
    -2147024809 — NOT 404. Treating only 404 as absent made Phase 3.1 fail
    its probe on every view it was about to create (seen live on a register
    deployment). Both probes must share one absent-detection helper so the
    next by-name getter cannot reintroduce this bug."""
    js = _generate_views_js(tmp_path)
    view_probe = js.split("async function readViewShape")[1].split("async function")[0]
    assert "isAbsent400(r.status, text)" in view_probe
    assert "return null" in view_probe
    assert "view shape probe failed" in view_probe


def test_view_query_comparison_tolerates_space_before_self_close(
    tmp_path: Path,
) -> None:
    """SharePoint's ViewQuery readback writes self-closing tags with a space
    (`<FieldRef Name="X" />` for a declared `<FieldRef Name="X"/>`), so the
    normalized comparison must collapse whitespace before `/>` as well as
    between tags — otherwise every created view immediately fails its own
    verification (seen live on a register deployment)."""
    js = _generate_views_js(tmp_path)
    normalizer = js.split("const normalizeViewQuery")[1].split("\n")[0]
    assert "replace(/\\s+\\/>/g, '/>')" in normalizer
    assert "replace(/>\\s+</g, '><')" in normalizer


def test_deploy_js_phase_3c_provisions_and_reconciles_views(tmp_path: Path) -> None:
    """Fields created through the REST field collection join no view, so a
    fresh deployment shows a Title-only default view. Declared views are part
    of the physical shape: Phase 3.1 creates missing views, reconciles
    ViewQuery/RowLimit/field order/default flag on existing ones (public
    views only — a same-name personal view fails closed), verifies by
    readback, and never touches undeclared views (user content, unlike exact
    ACLs)."""
    js = _generate_views_js(tmp_path)
    assert f"Starting Phase {pn('views')}: views" in js
    assert "const deployView = async (view)" in js
    assert "mapLanes(SCHEMA.views, (view) => view.list, deployView" in js
    # create path
    assert "'SP.View'" in js
    assert "PersonalView: false" in js
    # reconcile paths
    assert "is a personal view; declared views must be public" in js
    assert "normalizeViewQuery" in js
    assert "removeallviewfields" in js
    assert "addviewfield('${odataName(name)}')" in js
    assert "DefaultView: true" in js
    # verification + fail-closed error routing
    assert "did not retain declared view setting(s)" in js
    assert "phase: '3.1'" in js
    # runs between field defaults and ACL work
    assert js.index(f"Starting Phase {pn('defaults')}") < js.index(
        f"Starting Phase {pn('views')}") < js.index(
        f"Starting Phase {pn('acls')}",
    )
    # rendered SCHEMA carries the view declaration
    assert '"Open risks"' in js
    assert '"set_default": true' in js


# --- Display names ----------------------------------------------------------


def _display_names_inputs(tmp_path: Path) -> tuple[Schema, MappingBundle]:
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Enum matrix_version {\n"
        '  "13.0"\n'
        "}\n"
        "Table Risk {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar [not null]\n"
        "  MatrixVersion matrix_version\n"
        "  RiskManReference nvarchar\n"
        "  RiskScore calculated_number\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Risk: { kind: List, base_template: 100, site_role: default }\n"
        "display_names:\n"
        "  mode: auto\n"
        "  overrides:\n"
        "    Risk:\n"
        '      RiskManReference: "RiskMan Reference"\n'
        "calculated_formulas:\n"
        "  Risk:\n"
        "    RiskScore: '=IF([MatrixVersion]=\"13.0\",1,"
        "IF([RiskManReference]=\"[MatrixVersion]\",2,3))'\n",
        encoding="utf-8",
    )
    return parse_dbml(tmp_path / "s.dbml"), load_mapping(tmp_path / "m.yaml")


def test_fields_carry_display_titles_and_create_with_internal_name(
    tmp_path: Path,
) -> None:
    """Rename-after-create: the field CREATE body keeps Title = internal name
    (locking a clean InternalName), while display_title carries the desired
    human-readable Title that reconciliation MERGEs afterwards. Overrides win
    over the auto split; with the feature off display_title == title."""
    from dbml_sharepoint.generators.jsgen import build_schema_json

    schema, bundle = _display_names_inputs(tmp_path)
    risk = next(
        lst for lst in build_schema_json(schema, bundle, "default")["lists"]
        if lst["title"] == "APP_Risk"
    )
    by_title = {f["title"]: f for f in risk["fields_phase1"]}
    assert by_title["MatrixVersion"]["display_title"] == "Matrix Version"
    assert by_title["RiskManReference"]["display_title"] == "RiskMan Reference"
    assert by_title["RiskScore"]["display_title"] == "Risk Score"
    # CREATE bodies keep the internal name so InternalName stays clean.
    assert by_title["MatrixVersion"]["body"]["Title"] == "MatrixVersion"

    off = parse_dbml(FIXTURES / "calculated.dbml")
    off_bundle = load_mapping(FIXTURES / "calculated-mapping.yaml")
    off_risk = next(
        lst for lst in build_schema_json(off, off_bundle, "default")["lists"]
    )
    assert all(f["display_title"] == f["title"] for f in off_risk["fields_phase1"])


def test_formula_references_rewritten_to_display_names(tmp_path: Path) -> None:
    """SharePoint resolves formula [refs] against DISPLAY names at write
    time, so once MatrixVersion displays as "Matrix Version" a formula
    saying [MatrixVersion] fails to create. Authors keep internal names;
    the build rewrites refs to display names — outside string literals only
    (bracket text inside a quoted constant is data)."""
    from dbml_sharepoint.generators.jsgen import build_schema_json

    schema, bundle = _display_names_inputs(tmp_path)
    risk = next(
        lst for lst in build_schema_json(schema, bundle, "default")["lists"]
        if lst["title"] == "APP_Risk"
    )
    formula = next(
        f["body"]["Formula"] for f in risk["fields_phase1"] if f["title"] == "RiskScore"
    )
    assert "[Matrix Version]" in formula
    assert "[RiskMan Reference]" in formula
    # The string literal "[MatrixVersion]" is data and stays verbatim.
    assert '"[MatrixVersion]"' in formula


def test_template_reconciles_title_to_display_title(tmp_path: Path) -> None:
    """The desired display Title is field.display_title (rename-after-create);
    field.title remains the immutable-InternalName expectation everywhere
    else, so probes and identity checks stay keyed on internal names."""
    js = _generate_views_js(tmp_path)
    # Synthetic reconcile callers (the built-in Title patch) carry no
    # display_title; comparing against undefined made every Title patch
    # "drift" forever (seen live). Desired title falls back to the internal.
    assert (
        "const desiredTitle = field.display_title != null ? field.display_title : field.title"
        in js
    )
    assert "actual.Title !== desiredTitle" in js
    assert "patchBody.Title = desiredTitle" in js
    assert "drift('Title', desiredTitle, actual.Title)" in js
    assert "actual.Title !== field.title" not in js
    # Immutable identity stays internal.
    assert "actual.InternalName !== field.title" in js


# --- Column formatting ------------------------------------------------------


def _formatting_inputs(tmp_path: Path) -> tuple[Schema, MappingBundle]:
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
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Risk: { kind: List, base_template: 100, site_role: default }\n"
        "column_formatting:\n"
        "  Risk:\n"
        "    Status: { elmType: div, txtContent: '@currentField' }\n",
        encoding="utf-8",
    )
    return parse_dbml(tmp_path / "s.dbml"), load_mapping(tmp_path / "m.yaml")


def test_fields_carry_compact_custom_formatter(tmp_path: Path) -> None:
    from dbml_sharepoint.generators.jsgen import build_schema_json

    schema, bundle = _formatting_inputs(tmp_path)
    risk = next(
        lst for lst in build_schema_json(schema, bundle, "default")["lists"]
        if lst["title"] == "APP_Risk"
    )
    by_title = {f["title"]: f for f in risk["fields_phase1"]}
    assert by_title["Status"]["custom_formatter"] == (
        '{"elmType":"div","txtContent":"@currentField"}'
    )
    assert by_title["Status"]["body"].get("CustomFormatter") is None
    # Undeclared columns carry an explicit null so the template never
    # touches a hand-applied format.
    assert by_title["Detail" if "Detail" in by_title else "Status"] is not None
    for f in risk["fields_phase1"]:
        if f["title"] != "Status":
            assert f["custom_formatter"] is None


def test_template_reconciles_custom_formatter(tmp_path: Path) -> None:
    """CustomFormatter rides the field reconcile: probed in the base
    $select, compared canonically (key order/whitespace-proof), narrowly
    MERGEd, drift-reported. Declared-null fields are never compared."""
    schema, bundle = _formatting_inputs(tmp_path)
    js = generate_deploy_js(
        schema=schema, bundle=bundle,
        release=load_release(FIXTURES / "release.yaml"),
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default",
        source_dbml="s.dbml",
        source_mtime="2026-05-04T00:00:00Z",
        generated_at="2026-05-04T00:00:00Z",
    )
    assert "const canonicalJson = " in js
    assert "'ReadOnlyField', 'Sealed', 'DefaultValue', 'CustomFormatter'" in js
    assert "field.custom_formatter != null" in js
    assert (
        "canonicalJson(actual.CustomFormatter) !== canonicalJson(field.custom_formatter)"
        in js
    )
    assert "patchBody.CustomFormatter = field.custom_formatter" in js
    assert "drift('CustomFormatter', field.custom_formatter, actual.CustomFormatter)" in js


def test_view_rows_carry_formatting_and_template_reconciles_it(tmp_path: Path) -> None:
    """Row formatting is a declared view setting: SCHEMA carries the compact
    JSON; Phase 3.1 compares canonically, MERGEs CustomFormatter, verifies by
    readback; views without a declaration are never touched."""
    from dbml_sharepoint.generators.jsgen import build_schema_json

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
        "views:\n"
        "  Risk:\n"
        "    - title: Hot\n"
        "      fields: [Title, Score]\n"
        "      formatting: { additionalRowClass: \"=if([$Score] >= 20, "
        "'sp-css-backgroundColor-BgCoral', '')\" }\n",
        encoding="utf-8",
    )
    schema = parse_dbml(tmp_path / "s.dbml")
    bundle = load_mapping(tmp_path / "m.yaml")
    row = build_schema_json(schema, bundle, "default")["views"][0]
    assert row["formatting"] == (
        '{"additionalRowClass":"=if([$Score] >= 20, \'sp-css-backgroundColor-BgCoral\', \'\')"}'
    )
    js = generate_deploy_js(
        schema=schema, bundle=bundle,
        release=load_release(FIXTURES / "release.yaml"),
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default",
        source_dbml="s.dbml",
        source_mtime="2026-05-04T00:00:00Z",
        generated_at="2026-05-04T00:00:00Z",
    )
    assert "$select=Id,Title,DefaultView,RowLimit,ViewQuery,PersonalView,CustomFormatter" in js
    assert "view.formatting != null" in js
    assert "CustomFormatter: view.formatting" in js
    # The view CustomFormatter lives in the view schema XML like ViewQuery,
    # so readback is XML-entity-encoded ('>=' returns as '&gt;=' — seen
    # live): compare via xmlDecode before canonical JSON, both sides.
    assert "const canonicalViewFormatter" in js
    assert (
        "canonicalViewFormatter(actual.CustomFormatter) !== canonicalViewFormatter(view.formatting)"
        in js
    )
    # Scoped to Phase 3.1: the FIELD-level comparison stays plain
    # canonicalJson (field CustomFormatter storage is not XML-encoded).
    phase3c = js.split(f"Starting Phase {pn('views')}")[1].split(f"Starting Phase {pn('forms')}")[0]
    assert "canonicalJson(actual.CustomFormatter)" not in phase3c


# --- Form formatting --------------------------------------------------------


def _form_formatting_inputs(tmp_path: Path) -> tuple[Schema, MappingBundle]:
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Risk {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar [not null]\n"
        "  ReviewDate date\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Risk: { kind: List, base_template: 100, site_role: default }\n"
        "display_names:\n"
        "  mode: auto\n"
        "form_formatting:\n"
        "  Risk:\n"
        "    body: { sections: [ { displayname: Core, fields: [Title, ReviewDate] } ] }\n",
        encoding="utf-8",
    )
    return parse_dbml(tmp_path / "s.dbml"), load_mapping(tmp_path / "m.yaml")


def test_date_default_today_reaches_field_defaults(tmp_path: Path) -> None:
    """A DBML date default (notably the dynamic '[today]') must land on the
    SP.FieldDateTime body and in SCHEMA.field_defaults — previously the
    DateTime branch silently dropped defaults the typemap carried."""
    from dbml_sharepoint.generators.jsgen import build_schema_json

    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Risk {\n  Id int [pk, increment]\n"
        "  Title nvarchar [not null]\n"
        "  LastReviewedDate date [default: '[today]']\n}\n",
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
    out = build_schema_json(schema, bundle, "default")
    defaults = {
        (d["list"], d["field"]): d["default_value"] for d in out["field_defaults"]
    }
    assert defaults[("APP_Risk", "LastReviewedDate")] == "[today]"
    field = next(
        f for f in out["lists"][0]["fields_phase1"]
        if f["title"] == "LastReviewedDate"
    )
    assert field["body"]["DefaultValue"] == "[today]"


def test_form_formatting_composed_with_display_rewrite(tmp_path: Path) -> None:
    """ClientFormCustomFormatter is a JSON string whose *JSONFormatter keys
    hold part JSON OBJECTS — the pane-native encoding (the Format pane
    displays string-encoded parts escaped; objects display clean, and the
    renderer accepts both). Body section field lists are the one place SP
    matches by DISPLAY name, so they are rewritten through the display
    map; only declared parts appear."""
    import json as jsonlib

    from dbml_sharepoint.generators.jsgen import build_schema_json

    schema, bundle = _form_formatting_inputs(tmp_path)
    rows = build_schema_json(schema, bundle, "default")["form_formatting"]
    assert [row["list"] for row in rows] == ["APP_Risk"]
    outer = jsonlib.loads(rows[0]["client_form_custom_formatter"])
    assert set(outer) == {"bodyJSONFormatter"}
    body = outer["bodyJSONFormatter"]
    assert isinstance(body, dict)                       # object, not string
    assert body["sections"][0]["fields"] == ["Title", "Review Date"]


def test_template_phase_3d_compare_is_encoding_agnostic(tmp_path: Path) -> None:
    """Sites deployed before the pane-native encoding carry string-encoded
    parts; canonicalFormFormatter must parse string parts before
    canonicalising so semantically-equal layouts compare equal in either
    encoding (no churn, no false readback failures)."""
    schema, bundle = _form_formatting_inputs(tmp_path)
    js = generate_deploy_js(
        schema=schema, bundle=bundle,
        release=load_release(FIXTURES / "release.yaml"),
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default",
        source_dbml="s.dbml",
        source_mtime="2026-05-04T00:00:00Z",
        generated_at="2026-05-04T00:00:00Z",
    )
    idx = js.index("const canonicalFormFormatter")
    block = js[idx:idx + 800]
    assert "typeof part === 'string'" in block
    assert "JSON.parse(part)" in block


def test_template_phase_3d_reconciles_form_formatting(tmp_path: Path) -> None:
    schema, bundle = _form_formatting_inputs(tmp_path)
    js = generate_deploy_js(
        schema=schema, bundle=bundle,
        release=load_release(FIXTURES / "release.yaml"),
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default",
        source_dbml="s.dbml",
        source_mtime="2026-05-04T00:00:00Z",
        generated_at="2026-05-04T00:00:00Z",
    )
    assert f"Starting Phase {pn('forms')}: form formatting" in js
    assert "for (const form of SCHEMA.form_formatting)" in js
    assert "contenttypes?$select=Name,StringId,ClientFormCustomFormatter" in js
    assert "ct.StringId.startsWith('0x01') && !ct.StringId.startsWith('0x0120')" in js
    assert "no default item content type found" in js
    assert "'SP.ContentType'" in js
    assert "canonicalFormFormatter" in js
    assert "did not retain declared form formatting" in js
    assert "phase: '3.2'" in js
    assert js.index(f"Starting Phase {pn('views')}") < js.index(
        f"Starting Phase {pn('forms')}") < js.index(
        f"Starting Phase {pn('acls')}",
    )


def test_list_validation_flows_to_schema_and_template(tmp_path: Path) -> None:
    """ValidationFormula/Message ride the declared list settings: rewritten
    to display names, probed in readListShape, compared via canonicalFormula
    and reconciled by the existing narrow list MERGE."""
    from dbml_sharepoint.generators.jsgen import build_schema_json

    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Enum status {\n"
        '  "Open"\n'
        '  "Closed"\n'
        "}\n"
        "Table Risk {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar [not null]\n"
        "  ClosureNote nvarchar\n"
        "  Status status\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Risk: { kind: List, base_template: 100, site_role: default }\n"
        "display_names:\n"
        "  mode: auto\n"
        "list_validation:\n"
        "  Risk:\n"
        "    when:\n"
        "      any_of:\n"
        "        - none_of:\n"
        "            - { field: Status, op: eq, value: Closed }\n"
        "        - { field: ClosureNote, op: is_not_null }\n"
        "    message: Closing needs a closure note.\n",
        encoding="utf-8",
    )
    schema = parse_dbml(tmp_path / "s.dbml")
    bundle = load_mapping(tmp_path / "m.yaml")
    risk = next(
        lst for lst in build_schema_json(schema, bundle, "default")["lists"]
        if lst["title"] == "APP_Risk"
    )
    # The implication "if closed then a closure note" as the grammar spells
    # it — any_of[none_of[antecedent], consequent] — with the null arm the
    # negation adds so blank rows are not silently excluded, and internal
    # names rewritten to display names, which is what SP resolves against.
    assert risk["validation_formula"] == (
        '=OR(OR(ISBLANK([Status]),[Status]<>"Closed"),NOT(ISBLANK([Closure Note])))'
    )
    assert risk["validation_message"] == "Closing needs a closure note."

    js = generate_deploy_js(
        schema=schema, bundle=bundle,
        release=load_release(FIXTURES / "release.yaml"),
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default",
        source_dbml="s.dbml",
        source_mtime="2026-05-04T00:00:00Z",
        generated_at="2026-05-04T00:00:00Z",
    )
    assert (
        "'EnableVersioning', 'EnableMinorVersions', 'MajorVersionLimit', "
        "'ValidationFormula', 'ValidationMessage'"
    ) in js
    # Validation reconciles AFTER the list's fields exist: the formula
    # references columns (by display name) that the same run creates and
    # renames — merging it with the pre-field list settings fails with
    # "The formula refers to a column that does not exist" (seen live).
    assert "async function reconcileListValidation" in js
    assert "list.validation_formula == null" in js
    assert "did not retain declared validation" in js
    assert "desired.ValidationFormula" not in js
    phase1 = js.split(f"Starting Phase {pn('lists')}")[1].split(
        f"Starting Phase {pn('lookups')}")[0]
    assert phase1.index("for (const col of list.fields_phase1)") < phase1.index(
        "await reconcileListValidation(list",
    )



def test_operator_effective_rights_diagnostic_after_cleanup() -> None:
    """List ACLs can LOOK correct while the signed-in operator still deletes
    happily — site collection admins and Full Control holders bypass list
    ACLs entirely (seen live: the deploying owner could delete despite a
    no-delete working level). After self-enrolment cleanup the script probes
    the operator's EffectiveBasePermissions per ACL'd list and logs
    delete/manage rights with the bypass explanation, so the operator knows
    member-level verification needs an ordinary member account."""
    js = _generate_simple_js()
    assert "/effectivebasepermissions" in js
    assert "Operator effective rights on" in js
    assert "bypass list ACLs" in js
    assert "ordinary member account" in js
    # Group-connected sites make every group owner a site collection admin
    # — invisible in Check Permissions, bypasses every list ACL. Say so.
    assert "_spPageContextInfo.isSiteAdmin" in js
    assert "site collection admin = " in js
    assert "owners of a group-connected site are site collection admins" in js
    # After cleanup, before DONE — enrolment would otherwise inflate rights.
    assert js.rindex("await removeSelfEnrollments()") < js.index(
        "Operator effective rights on",
    ) < js.index("Deployment complete.")


# --- UI hardening: sealed columns + list deletion block ----------------------


def _hardening_inputs(tmp_path: Path) -> tuple[Schema, MappingBundle]:
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Risk {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar [not null]\n"
        "  Detail nvarchar\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Risk: { kind: List, base_template: 100, site_role: default }\n"
        "seal_columns: true\n"
        "prevent_list_deletion: true\n",
        encoding="utf-8",
    )
    return parse_dbml(tmp_path / "s.dbml"), load_mapping(tmp_path / "m.yaml")


def test_hardening_flags_flow_to_schema(tmp_path: Path) -> None:
    from dbml_sharepoint.generators.jsgen import build_schema_json

    schema, bundle = _hardening_inputs(tmp_path)
    risk = next(
        lst for lst in build_schema_json(schema, bundle, "default")["lists"]
        if lst["title"] == "APP_Risk"
    )
    assert risk["prevent_deletion"] is True
    assert all(f["seal"] is True for f in risk["fields_phase1"])


def test_template_brackets_writes_with_unseal_and_seal_phases(tmp_path: Path) -> None:
    """Sealed columns block UI schema edits even for site admins — the
    strongest defense available when team owners are unavoidably site
    collection admins (group-connected sites). Design: a maintenance unseal
    after Phase 1.2 leaves every existing write path untouched, and Phase 4.1
    re-seals and verifies after all field writes (3/3b/3d) are done. The
    immutable-shape gate tolerates sealed only for declared-seal fields."""
    schema, bundle = _hardening_inputs(tmp_path)
    js = generate_deploy_js(
        schema=schema, bundle=bundle,
        release=load_release(FIXTURES / "release.yaml"),
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default",
        source_dbml="s.dbml",
        source_mtime="2026-05-04T00:00:00Z",
        generated_at="2026-05-04T00:00:00Z",
    )
    assert "Maintenance unseal" in js
    assert f"Starting Phase {pn('seal')}: seal declared columns" in js
    assert "Sealed: false" in js
    assert "Sealed: true" in js
    assert "did not retain sealed state" in js
    assert "actual.Sealed && !field.seal" in js
    assert js.index(f"Starting Phase {pn('security')}") < js.index("Maintenance unseal") < js.index(
        f"Starting Phase {pn('lists')}",
    )
    assert js.index(f"Starting Phase {pn('forms')}") < js.index(
        f"Starting Phase {pn('seal')}",
    ) < js.index(f"Starting Phase {pn('acls')}")


def test_template_blocks_list_deletion_when_declared(tmp_path: Path) -> None:
    """AllowDeletion=false makes the LIST object undeletable through the UI
    even for admins — friction, not enforcement, honestly labeled. Isolated
    probe/MERGE so an unsupported tenant surface fails only this step."""
    schema, bundle = _hardening_inputs(tmp_path)
    js = generate_deploy_js(
        schema=schema, bundle=bundle,
        release=load_release(FIXTURES / "release.yaml"),
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default",
        source_dbml="s.dbml",
        source_mtime="2026-05-04T00:00:00Z",
        generated_at="2026-05-04T00:00:00Z",
    )
    assert "list.prevent_deletion" in js
    assert "$select=AllowDeletion" in js
    assert "AllowDeletion: false" in js
    assert "did not retain AllowDeletion" in js



def test_view_existence_check_enumerates_per_list(tmp_path: Path) -> None:
    """views/getbytitle on an absent view answers HTTP 400 — handled by
    isAbsent400, but the browser paints the failed request red and
    operators read it as a deployment error (seen live). The existence
    check must come from ONE views?$select enumeration per list (always
    200); getbytitle remains only for post-create reads, when the view
    exists."""
    js = _generate_views_js(tmp_path)
    assert "/views?$select=" in js
    assert "async function listViewShapes" in js
    assert "await listViewShapes(listPath)" in js
    # The existence decision must NOT come from a per-title shape probe.
    existence = js.split("const deployView = async (view)")[1]
    creating = existence.split("Creating view")[0]
    assert "readViewShape(viewUrl)" not in creating


def test_field_shapes_served_from_per_list_enumeration(tmp_path: Path) -> None:
    """Two live findings, one mechanism: absent-field by-name GETs answer 400
    (painted red, read as failures), and bulk probe loops paid one GET per
    column per phase. Base shapes now come from ONE fields enumeration per
    list; probes reflect phase-start state (each field-touching phase
    invalidates); verify-after-write reads pass fresh=true and bypass the
    cache."""
    js = _generate_views_js(tmp_path)
    assert "async function listFieldShapes" in js
    assert "fields?$select=${_FIELD_SHAPE_SELECT}" in js
    assert "const invalidateFieldShapes" in js
    # Phase starts + both field-creation sites re-snapshot.
    assert js.count("invalidateFieldShapes();") >= 7
    probe = js.split("async function readFieldShape")[1].split("if (!shape")[0]
    assert "listFieldShapes(listName)" in probe
    assert "fresh" in probe
    # Post-write verifies bypass the cache.
    assert "readFieldShape(listName, field.title, field, true)" in js


def test_seal_phases_run_lanes_and_verify_via_enumeration(tmp_path: Path) -> None:
    """Live DEBUG timing: seal 13.3s + unseal 7.6s of a 52s run. Both now
    lane per list (same-list field MERGEs race into save conflicts). Seal
    verification never trusts phase-start state, but it no longer pays one
    fresh GET per column: the lane invalidates ITS list's snapshot after
    writing and one fresh enumeration serves every column's readback."""
    js = _generate_views_js(tmp_path)
    assert "mapLanes([...sealByList.entries()]" in js
    assert "invalidateFieldShapes(listTitle);  // verify from post-write state" in js
    # Per-list (argument) invalidation must exist alongside the full reset.
    assert "delete fieldShapesByList[listName];" in js
    # Unseal lanes per list too.
    assert "mapLanes(sealDeclared, ([listTitle]) => listTitle" in js
    # Preflight (read-only) lanes both waves; field wave waits on shapes.
    assert "mapLanes(SCHEMA.lists, (list) => list.title" in js
    assert "SCHEMA.lists.filter((list) => preflightListShapes[list.title])" in js


def test_view_verify_rides_one_fresh_readback(tmp_path: Path) -> None:
    """Steady-state views paid three decision GETs per view (formatting
    current, preFlag, viewfields readback) on top of the fail-closed verify.
    Decision reads now reuse the phase-start enumeration shape; the verify
    stays fresh and carries ViewFields via $expand — one GET, same gate."""
    js = _generate_views_js(tmp_path)
    assert "const current = existing || await readViewShape(viewUrl);" in js
    assert "const preFlag = existing || await readViewShape(viewUrl);" in js
    assert "(actual.ViewFields && actual.ViewFields.Items && actual.ViewFields.Items.results)" in js


def test_digest_is_cached_until_near_expiry(tmp_path: Path) -> None:
    js = _generate_views_js(tmp_path)
    assert "digestExpiresAt" in js
    assert "FormDigestTimeoutSeconds" in js


def test_view_fields_ride_the_enumeration(tmp_path: Path) -> None:
    js = _generate_views_js(tmp_path)
    assert "$expand=ViewFields" in js
    assert "existing.ViewFields.Items.results" in js


def test_views_created_with_slug_then_renamed(tmp_path: Path) -> None:
    """A view's .aspx name is fixed at creation from its Title, so creating
    with the display title bakes %20 into the URL forever. Create with the
    URL slug, then MERGE Title to the declared display title (renames never
    touch the URL). Existing escaped-URL declared views are migrated by
    recreate (deployer-owned), with the URL in the fail-closed drift gate."""
    js = _generate_views_js(tmp_path)
    assert "Title: view.url_slug" in js
    assert "ServerRelativeUrl" in js
    # Rename to the declared title after create (skipped when identical).
    assert "view.url_slug !== view.title" in js
    # Migration path for existing views under an escaped URL.
    assert "clean URL" in js
    assert "'X-HTTP-Method': 'DELETE'" in js
    # Fail closed: URL basename must verify like every declared setting.
    assert "Url (declared" in js


def test_deploy_runs_per_list_lanes(tmp_path: Path) -> None:
    """Concurrent schema writes to the SAME list race into save conflicts;
    different lists are independent. So the parallelism unit is the list:
    mapLanes runs one strictly-sequential lane per list, lanes concurrent."""
    js = _generate_views_js(tmp_path)
    assert "async function mapLanes" in js
    assert "mapLanes(SCHEMA.views, (view) => view.list" in js
    # Lists phase: wave 1 sequential (lookup targets need GUIDs), wave 2
    # field provisioning in per-list lanes.
    assert "mapLanes(fieldWork, (list) => list.title" in js


def test_debug_flag_default_off(tmp_path: Path) -> None:
    """Timing diagnostics ship in every bundle behind `const DEBUG = false`
    (operators flip it in the pasted script; no rebuild). Phase timings and
    the request counter record always; printing is DEBUG-only."""
    js = _generate_views_js(tmp_path)
    assert "const DEBUG = false;" in js
    assert "const dbg = " in js
    assert "requestCount += 1" in js
    assert "markPhase(" in js
    assert "console.table" in js
    assert "elapsedSeconds" in js


def test_widths_apply_via_guarded_setviewxml(tmp_path: Path) -> None:
    """Widths ride the whole-document SetViewXml() surface the modern Lists
    UI uses (live capture 2026-07-24). Property MERGEs on ListViewXml are
    DESTRUCTIVE (live finding: every view reset to the blank default), so
    the generated step must be read → splice ONLY ColumnWidth → write, with
    a diff-guard refusing any other change and a fail-closed readback."""
    js = _generate_views_js(tmp_path)
    # Read side: the server's own full serialization, fresh each time.
    assert "$select=ListViewXml" in js
    # Write side: the method call, never a MERGE of ListViewXml.
    assert "/setviewxml()" in js
    assert "ListViewXml:" not in js  # no MERGE body carrying the property
    # Splice + guard + fail-closed verify.
    assert "<ColumnWidth>" in js
    assert "stripColumnWidth" in js
    assert "widths splice guard" in js
    assert "did not retain declared column widths" in js


def test_retired_columns_leave_views_but_stay_deployed() -> None:
    """The end-to-end proof that retirement needs no jsgen change: the
    column is still created and still deployer-managed (so the drift audit
    stays clean) but it is hidden from the New form, carries the retired
    suffix, and has left every declared view."""
    from dbml_sharepoint.generators.jsgen import build_schema_json

    schema = parse_dbml(FIXTURES / "retired.dbml")
    bundle = load_mapping(FIXTURES / "retired-mapping.yaml")

    schema_json = build_schema_json(schema, bundle, "default")

    board = next(lst for lst in schema_json["lists"] if lst["title"] == "APP_Board")
    ops = next(f for f in board["fields_phase1"] if f["title"] == "OperationsStatus")
    # Present on the Edit and Display forms, absent from New: [$ID] is empty
    # only while the item is being created.
    assert ops["client_validation_formula"] == "=if([$ID] != '', 'true', 'false')"
    assert ops["display_title"] == "Operations Status (retired)"
    live = next(
        f for f in board["fields_phase1"] if f["title"] == "SiteServicesStatus"
    )
    # `declared` reconcile: a live column of the same list is untouched.
    assert live["client_validation_formula"] == UNMANAGED
    assert live["display_title"] == "Site Services Status"

    view = next(v for v in schema_json["views"] if v["title"] == "Heat grid")
    assert view["view_fields"] == ["BoardDate", "SiteServicesStatus"]


def test_view_fields_reach_jsgen_flat_and_resolved(tmp_path: Path) -> None:
    """jsgen has no field-set awareness by design: ViewDef.fields is always
    already a flat, resolved, de-duplicated list of internal column names by
    the time build_schema_json reads it. A failure here means expansion has
    leaked past the loader."""
    from dbml_sharepoint.generators.jsgen import build_schema_json

    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Board {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar [not null]\n"
        "  BoardDate date\n"
        "  OperationsStatus nvarchar\n"
        "  WorkforceStatus nvarchar\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Board: { kind: List, base_template: 100, site_role: default }\n"
        "field_sets:\n"
        "  Board:\n"
        "    header:   [Title, BoardDate]\n"
        "    statuses: [OperationsStatus, WorkforceStatus]\n"
        "views:\n"
        "  Board:\n"
        "    - title: Heat grid\n"
        '      fields: ["@header", "@statuses", BoardDate]\n',
        encoding="utf-8",
    )
    schema = parse_dbml(tmp_path / "s.dbml")
    bundle = load_mapping(tmp_path / "m.yaml")
    schema_json = build_schema_json(schema, bundle, "default")
    view_fields = schema_json["views"][0]["view_fields"]
    assert view_fields == [
        "Title", "BoardDate", "OperationsStatus", "WorkforceStatus",
    ]
    assert not any(name.startswith("@") for name in view_fields)
