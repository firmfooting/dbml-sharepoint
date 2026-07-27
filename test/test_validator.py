# test/test_validator.py
from pathlib import Path
from typing import Any, ClassVar

from dbml_sharepoint.analysis.validator import (
    Finding,
    validate,
    validate_against_mapping,
    validate_all,
)
from dbml_sharepoint.extension import BaseExtension
from dbml_sharepoint.model.mapping_loader import (
    CrossSiteRef,
    CustomPermissionLevel,
    EntityMapping,
    ListPermissionPolicy,
    Mapping,
    MappingBundle,
    PermissionsConfig,
    Principal,
    RoleAssignment,
    Versioning,
    load_mapping,
)
from dbml_sharepoint.model.parser import Column, EnumDef, Reference, Schema, Table, parse_dbml


def test_style_map_keys_must_be_enum_members(tmp_path: Path) -> None:
    """A severity/pill map naming a choice the column's enum does not
    contain is a declaration bug — same ethos as [$Field] checking."""
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Enum status {\n"
        '  "Open"\n'
        '  "Closed"\n'
        "}\n"
        "Table Risk {\n  Id int [pk, increment]\n"
        "  Title nvarchar [not null]\n  Status status\n}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Risk: { kind: List, base_template: 100, site_role: default }\n"
        "column_formatting:\n"
        "  Risk:\n"
        "    Status: { style: severity, map: { Open: low, Bogus: good } }\n",
        encoding="utf-8",
    )
    schema = parse_dbml(tmp_path / "s.dbml")
    bundle = load_mapping(tmp_path / "m.yaml")
    findings = validate_against_mapping(schema, bundle)
    assert any(
        "Bogus" in f.message and "column_formatting[Risk].Status" in f.message
        for f in findings if f.severity == "error"
    )

def test_data_bar_color_by_map_keys_must_be_enum_members(tmp_path: Path) -> None:
    """The data-bar colour translation is checked like severity maps: a
    map key the SOURCE column's enum cannot produce is a declaration bug
    (the bar would silently fall back to neutral for a value that never
    occurs while the intended value goes unmapped)."""
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Enum rating {\n"
        '  "Low"\n'
        '  "High"\n'
        "}\n"
        "Table Risk {\n  Id int [pk, increment]\n"
        "  Title nvarchar [not null]\n  Rating rating\n  Score int\n}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Risk: { kind: List, base_template: 100, site_role: default }\n"
        "column_formatting:\n"
        "  Risk:\n"
        "    Score: { style: data-bar, max: 25,\n"
        "             color_by: { field: Rating, map: { Low: good, Bogus: blocked } } }\n",
        encoding="utf-8",
    )
    schema = parse_dbml(tmp_path / "s.dbml")
    bundle = load_mapping(tmp_path / "m.yaml")
    findings = validate_against_mapping(schema, bundle)
    assert any(
        "Bogus" in f.message and "column_formatting[Risk].Score" in f.message
        for f in findings if f.severity == "error"
    )
    # The valid key raises nothing.
    assert not any("'Low'" in f.message for f in findings if f.severity == "error")


def test_formatter_may_reference_system_columns(tmp_path: Path) -> None:
    """[$Created]/[$Modified]/[$ID]/[$Author]/[$Editor] always exist on a
    list; formatter references to them must not be rejected, while a
    genuinely unknown reference still errors."""
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Risk {\n  Id int [pk, increment]\n"
        "  Title nvarchar [not null]\n  Gap int\n}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Risk: { kind: List, base_template: 100, site_role: default }\n"
        "column_formatting:\n"
        "  Risk:\n"
        "    Gap:\n"
        "      elmType: div\n"
        '      txtContent: "=toLocaleDateString([$Created] + 1)"\n',
        encoding="utf-8",
    )
    schema = parse_dbml(tmp_path / "s.dbml")
    bundle = load_mapping(tmp_path / "m.yaml")
    findings = validate_against_mapping(schema, bundle)
    assert not any("Created" in f.message for f in findings if f.severity == "error")
    (tmp_path / "m2.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Risk: { kind: List, base_template: 100, site_role: default }\n"
        "column_formatting:\n"
        "  Risk:\n"
        "    Gap:\n"
        "      elmType: div\n"
        '      txtContent: "=[$Nope]"\n',
        encoding="utf-8",
    )
    findings2 = validate_against_mapping(schema, load_mapping(tmp_path / "m2.yaml"))
    assert any("Nope" in f.message for f in findings2 if f.severity == "error")


FIXTURES = Path(__file__).parent / "fixtures"

RESERVED_NAMES = {"Created", "Modified", "Editor", "Author", "Attachments", "_UIVersion"}


def _schema(*tables: Table, enums: list[EnumDef] | None = None) -> Schema:
    return Schema(tables=list(tables), enums=enums or [])


def test_unknown_ref_target_is_error() -> None:
    table = Table(name="Task", columns=[
        Column(name="Id", type="int", is_pk=True, is_auto_increment=True),
        Column(name="Project", type="int", ref=Reference("Missing", "Id")),
    ])
    findings = validate(_schema(table))
    assert any(f.severity == "error" and "Missing" in f.message for f in findings)


def test_legacy_choice_type_is_error() -> None:
    table = Table(name="Task", columns=[
        Column(name="Id", type="int", is_pk=True, is_auto_increment=True),
        Column(name="Status", type="choice"),
    ])
    findings = validate(_schema(table))
    assert any(f.severity == "error" and "legacy" in f.message.lower() for f in findings)


def test_unknown_type_is_error() -> None:
    table = Table(name="Task", columns=[
        Column(name="Id", type="int", is_pk=True, is_auto_increment=True),
        Column(name="Bad", type="frobnicate"),
    ])
    findings = validate(_schema(table))
    assert any(f.severity == "error" and "frobnicate" in f.message for f in findings)


def test_reserved_author_is_error() -> None:
    table = Table(name="PaperRegister", columns=[
        Column(name="Id", type="int", is_pk=True, is_auto_increment=True),
        Column(name="Author", type="person"),
    ])
    findings = validate(_schema(table))
    assert any(f.severity == "error" and "Author" in f.message for f in findings)


def test_unique_richtext_is_warning() -> None:
    table = Table(name="Note", columns=[
        Column(name="Id", type="int", is_pk=True, is_auto_increment=True),
        Column(name="Body", type="richtext", unique=True),
    ])
    findings = validate(_schema(table))
    assert any(f.severity == "warning" and "richtext" in f.message.lower() for f in findings)


def test_longtext_is_known_but_unique_is_warning() -> None:
    table = Table(name="ConnectorState", columns=[
        Column(name="Id", type="int", is_pk=True, is_auto_increment=True),
        Column(name="OpaqueValue", type="longtext", unique=True),
    ])

    findings = validate(_schema(table))

    assert not any(f.severity == "error" and "longtext" in f.message for f in findings)
    assert any(f.severity == "warning" and "longtext" in f.message for f in findings)


def test_orphan_enum_is_warning() -> None:
    table = Table(name="Task", columns=[
        Column(name="Id", type="int", is_pk=True, is_auto_increment=True),
    ])
    findings = validate(_schema(table, enums=[EnumDef(name="status", members=["a"])]))
    assert any(f.severity == "warning" and "orphan" in f.message.lower() for f in findings)


def test_enum_default_not_in_members_is_error() -> None:
    """An enum-typed column whose default is not one of the enum's declared
    members must be rejected at validate() time, not deferred to a deploy-time
    field-creation failure."""
    table = Table(name="Task", columns=[
        Column(name="Id", type="int", is_pk=True, is_auto_increment=True),
        Column(name="Status", type="status", default="Nope"),
    ])
    findings = validate(_schema(
        table, enums=[EnumDef(name="status", members=["Open", "Closed"])],
    ))
    assert any(
        f.severity == "error" and "Status" in f.message and "Nope" in f.message
        for f in findings
    )


def test_enum_default_in_members_is_ok() -> None:
    """A valid enum default must not produce a default-related error."""
    table = Table(name="Task", columns=[
        Column(name="Id", type="int", is_pk=True, is_auto_increment=True),
        Column(name="Status", type="status", default="Open"),
    ])
    findings = validate(_schema(
        table, enums=[EnumDef(name="status", members=["Open", "Closed"])],
    ))
    assert not any(
        f.severity == "error" and "Status" in f.message and "default" in f.message.lower()
        for f in findings
    )


def test_enum_source_with_no_matching_dbml_enum_is_warning() -> None:
    """An enum_sources entry with no
    matching DBML enum is a warning, not an error — the schema simply hasn't
    defined that enum yet, which by itself isn't wrong. simple.dbml has no
    'topic' enum, but the fixture mapping configures enum_sources['topic']."""
    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    findings = validate_against_mapping(schema, bundle)
    assert any(
        f.severity == "warning" and "topic" in f.message.lower() for f in findings
    )
    assert not any(
        f.severity == "error" and "topic" in f.message.lower() for f in findings
    )


def test_enum_source_mismatch_is_error_listing_both_sides() -> None:
    """A DBML enum whose members differ from the configured enum_sources
    values is an error, and the message must list both the DBML members and
    the configured YAML members so the mismatch is diagnosable without
    cross-referencing files."""
    schema = parse_dbml(FIXTURES / "simple.dbml")
    schema.enums.append(EnumDef(name="topic", members=["OnlyOne"]))
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    findings = validate_against_mapping(schema, bundle)
    assert any(
        f.severity == "error"
        and "OnlyOne" in f.message
        and "Strategy" in f.message
        and "Other" in f.message
        for f in findings
    )


def test_enum_source_check_is_generic_not_hardcoded_to_topic() -> None:
    """Regression: Task 7 replaces the 'topic'-only special-case with a loop
    over every bundle.enum_choices entry. Prove a second, differently-named
    enum_sources entry is cross-checked too."""
    schema = parse_dbml(FIXTURES / "simple.dbml")
    schema.enums.append(EnumDef(name="priority", members=["Low", "High"]))
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    bundle.enum_choices["priority"] = ["Low", "Medium", "High"]
    findings = validate_against_mapping(schema, bundle)
    assert any(
        f.severity == "error" and "priority" in f.message and "High" in f.message
        for f in findings
    )


def test_mapping_references_unknown_entity_is_error(tmp_path: object) -> None:
    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    # simple.dbml has Project + Task; mapping fixture also has Project + Task. OK.
    findings = validate_against_mapping(schema, bundle)
    assert all(f.severity != "error" or "unknown" not in f.message.lower() for f in findings)


def test_schema_table_missing_from_mapping_is_error() -> None:
    """Regression: a DBML table with no mapping entry must fail the build.
    build_schema_json silently skips unmapped tables, so without this check a
    newly-added schema entity would be omitted from the deploy plan while the
    build still succeeded."""
    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    del bundle.mapping.entities["Task"]
    findings = validate_against_mapping(schema, bundle)
    assert any(
        f.severity == "error" and "Task" in f.message and "mapping" in f.message.lower()
        for f in findings
    )


def test_indexed_column_unknown_entity_is_error() -> None:
    """indexed_columns keyed by a table that is not in the schema must be an
    error; jsgen silently ignores unknown keys, so the index would never be
    applied."""
    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    bundle.mapping.indexed_columns["NotATable"] = ["Whatever"]
    findings = validate_against_mapping(schema, bundle)
    assert any(
        f.severity == "error" and "NotATable" in f.message for f in findings
    )


def test_indexed_column_unknown_column_is_error() -> None:
    """Regression: an indexed_columns entry naming a nonexistent column passed
    validation and emitted a Phase 2.3 patch against a missing SP field, failing
    late in the browser."""
    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    bundle.mapping.indexed_columns["Task"] = ["DueDate", "NoSuchColumn"]
    findings = validate_against_mapping(schema, bundle)
    assert any(
        f.severity == "error" and "NoSuchColumn" in f.message for f in findings
    )
    # The valid sibling entry must not be flagged.
    assert not any("DueDate" in f.message for f in findings)


def test_indexed_column_cross_site_logical_name_is_error() -> None:
    """A cross-site column's LOGICAL name never exists in SP — it is expanded
    to <col>Abbreviation / <col>SiteUrl. Indexing the logical name must be an
    error; indexing an expanded name is valid."""
    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    bundle.mapping.cross_site_reference_columns.append(
        CrossSiteRef(entity="Task", column="Project"),
    )
    bundle.mapping.indexed_columns["Task"] = ["Project"]
    findings = validate_against_mapping(schema, bundle)
    assert any(
        f.severity == "error"
        and "Project" in f.message
        and "indexed_columns" in f.message
        for f in findings
    )

    # Expanded names are the real rendered fields and must pass.
    bundle.mapping.indexed_columns["Task"] = ["ProjectAbbreviation", "ProjectSiteUrl"]
    findings = validate_against_mapping(schema, bundle)
    assert not any(
        f.severity == "error" and "indexed_columns" in f.message for f in findings
    )


def test_default_policy_site_role_must_be_known() -> None:
    """list_permissions.default.site_role, when set, must be a known role."""
    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    assert bundle.mapping.permissions is not None
    bundle.mapping.permissions.default_policy_site_role = "comittee"
    findings = validate_against_mapping(schema, bundle)
    assert any(
        f.severity == "error" and "comittee" in f.message for f in findings
    )


def test_unknown_base_permission_in_custom_level_is_error() -> None:
    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    # Inject a bad permission name into the custom level.
    bundle.mapping.permissions = PermissionsConfig(
        levels=[CustomPermissionLevel(
            name="BadLevel",
            description="test",
            base_permissions=["ViewListItems", "NotARealPermission"],
        )],
        groups=[],
        default_policy=None,
        overrides={},
    )
    findings = validate_against_mapping(schema, bundle)
    assert any(
        f.severity == "error" and "NotARealPermission" in f.message
        for f in findings
    )


def test_assignment_referencing_undeclared_level_is_error() -> None:
    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    bundle.mapping.permissions = PermissionsConfig(
        levels=[],
        groups=[],
        default_policy=ListPermissionPolicy(
            break_inheritance=True,
            assignments=[
                RoleAssignment(
                    principal=Principal(kind="associated_owner_group"),
                    level="NonExistentLevel",
                ),
            ],
        ),
        overrides={},
    )
    findings = validate_against_mapping(schema, bundle)
    assert any(
        f.severity == "error" and "NonExistentLevel" in f.message
        for f in findings
    )


def test_principal_group_using_associated_alias_is_error() -> None:
    """Regression: `principal: {kind: group, name: "Site Owners"}` passed
    validation, but Phase 4.2 resolves kind=group via sitegroups/getbyname and
    on real sites the associated groups are named '<SiteTitle> Owners' etc.,
    so the deploy failed at role assignment. The validator must reject the
    three built-in aliases (exact, case-insensitive) and direct the author to
    the corresponding associated_* principal kind."""
    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    cases = {
        "Site Owners": "associated_owner_group",
        "site members": "associated_member_group",
        "SITE VISITORS": "associated_visitor_group",
    }
    for alias, suggested_kind in cases.items():
        bundle.mapping.permissions = PermissionsConfig(
            levels=[],
            groups=[],
            default_policy=ListPermissionPolicy(
                break_inheritance=True,
                assignments=[
                    RoleAssignment(
                        principal=Principal(kind="group", name=alias),
                        level="Contribute",
                    ),
                ],
            ),
            overrides={},
        )
        findings = validate_against_mapping(schema, bundle)
        assert any(
            f.severity == "error"
            and alias in f.message
            and suggested_kind in f.message
            for f in findings
        ), f"expected alias rejection for {alias!r}"


def test_principal_custom_group_name_still_passes() -> None:
    """Legitimate custom group principals (declared in `groups`) must not be
    affected by the associated-alias rejection. The fixture's default policy
    assigns to 'List Maintainer'."""
    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    findings = validate_against_mapping(schema, bundle)
    assert not any("List Maintainer" in f.message for f in findings)


def test_override_key_referencing_missing_entity_is_error() -> None:
    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    bundle.mapping.permissions = PermissionsConfig(
        levels=[],
        groups=[],
        default_policy=None,
        overrides={
            "DoesNotExist": ListPermissionPolicy(
                break_inheritance=True,
                assignments=[
                    RoleAssignment(
                        principal=Principal(kind="associated_owner_group"),
                        level="Contribute",
                    ),
                ],
            ),
        },
    )
    findings = validate_against_mapping(schema, bundle)
    assert any(
        f.severity == "error" and "DoesNotExist" in f.message
        for f in findings
    )


def test_lookup_target_without_title_or_display_column_is_error() -> None:
    """A1: a lookup into a target list that has no Title column and no
    display_column would render blank in SP (LookupField defaults to the empty
    Title). The validator must flag it and a declared display_column clears it."""
    def _bundle(display: str | None) -> MappingBundle:
        entities = {
            "Membership": EntityMapping(
                name="Membership", kind="List", base_template=100,
                site_role="default", display_column=display,
            ),
            "Meeting": EntityMapping(
                name="Meeting", kind="List", base_template=100, site_role="default",
            ),
        }
        mapping = Mapping(
            prefix="APP_", prefix_owner="", prefix_registry="", entities=entities,
            cross_site_reference_columns=[], indexed_columns={},
            versioning_default=Versioning(True, 500, False), versioning_overrides={},
            enum_sources={}, watched_lists=[],
        )
        return MappingBundle(
            mapping=mapping, enum_choices={}, retention_policies={},
            retention_list_defaults={},
        )

    schema = _schema(
        Table(name="Membership", columns=[
            Column(name="Id", type="int", is_pk=True, is_auto_increment=True),
            Column(name="DisplayName", type="nvarchar", required=True),
        ]),
        Table(name="Meeting", columns=[
            Column(name="Id", type="int", is_pk=True, is_auto_increment=True),
            Column(name="Title", type="nvarchar", required=True),
            Column(name="Chair", type="int", ref=Reference("Membership", "Id")),
        ]),
    )

    findings = validate_against_mapping(schema, _bundle(None))
    assert any(
        f.severity == "error" and "Chair" in f.message
        and "Membership" in f.message and "display_column" in f.message
        for f in findings
    )
    ok = validate_against_mapping(schema, _bundle("DisplayName"))
    assert not any(
        f.severity == "error" and "display_column" in f.message for f in ok
    )


def test_lookup_display_column_must_name_a_real_target_column() -> None:
    """PR #43 review: a mapping may set display_column, but if the named column
    does not exist on the target table (typo, or the column was removed) jsgen
    emits LookupField=<bad name> and the deploy fails at runtime. The validator
    must catch it — including when the target also has a Title column, since
    jsgen prefers display_column over Title."""
    def _bundle(display: str, *, target_has_title: bool = False) -> MappingBundle:
        entities = {
            "Meeting": EntityMapping(
                name="Meeting", kind="List", base_template=100, site_role="default",
            ),
            "Membership": EntityMapping(
                name="Membership", kind="List", base_template=100,
                site_role="default", display_column=display,
            ),
        }
        mapping = Mapping(
            prefix="APP_", prefix_owner="", prefix_registry="", entities=entities,
            cross_site_reference_columns=[], indexed_columns={},
            versioning_default=Versioning(True, 500, False), versioning_overrides={},
            enum_sources={}, watched_lists=[],
        )
        return MappingBundle(
            mapping=mapping, enum_choices={}, retention_policies={},
            retention_list_defaults={},
        )

    membership_cols = [
        Column(name="Id", type="int", is_pk=True, is_auto_increment=True),
        Column(name="DisplayName", type="nvarchar", required=True),
    ]
    schema = _schema(
        Table(name="Meeting", columns=[
            Column(name="Id", type="int", is_pk=True, is_auto_increment=True),
            Column(name="Title", type="nvarchar", required=True),
            Column(name="Chair", type="int", ref=Reference("Membership", "Id")),
        ]),
        Table(name="Membership", columns=membership_cols),
    )

    bad = validate_against_mapping(schema, _bundle("DisplayNam"))  # typo
    assert any(
        f.severity == "error" and "DisplayNam" in f.message
        and "display_column" in f.message
        for f in bad
    )
    ok = validate_against_mapping(schema, _bundle("DisplayName"))
    assert not any(f.severity == "error" and "display_column" in f.message for f in ok)


def test_cross_site_role_lookup_is_error() -> None:
    """A7: a plain lookup whose source and target map to different site_roles
    (one role ↔ another) can never be a SharePoint lookup — lookups cannot span
    webs. It must error unless declared in cross_site_reference_columns (which
    expands it to a Choice+URL pair instead of a lookup)."""
    def _bundle(cross_site: list[CrossSiteRef]) -> MappingBundle:
        entities = {
            "Meeting": EntityMapping(
                name="Meeting", kind="List", base_template=100, site_role="default",
            ),
            "FlowRunLog": EntityMapping(
                name="FlowRunLog", kind="HubOnlyList", base_template=100, site_role="admin",
            ),
        }
        mapping = Mapping(
            prefix="APP_", prefix_owner="", prefix_registry="", entities=entities,
            cross_site_reference_columns=cross_site, indexed_columns={},
            versioning_default=Versioning(True, 500, False), versioning_overrides={},
            enum_sources={}, watched_lists=[],
        )
        return MappingBundle(
            mapping=mapping, enum_choices={}, retention_policies={},
            retention_list_defaults={},
        )

    schema = _schema(
        Table(name="Meeting", columns=[
            Column(name="Id", type="int", is_pk=True, is_auto_increment=True),
            Column(name="Title", type="nvarchar", required=True),
            Column(name="Log", type="int", ref=Reference("FlowRunLog", "Id")),
        ]),
        Table(name="FlowRunLog", columns=[
            Column(name="Id", type="int", is_pk=True, is_auto_increment=True),
            Column(name="Title", type="nvarchar", required=True),
        ]),
    )
    findings = validate_against_mapping(schema, _bundle([]))
    assert any(
        f.severity == "error" and "Log" in f.message and "site_role" in f.message
        and "cross_site" in f.message
        for f in findings
    )
    ok = validate_against_mapping(
        schema, _bundle([CrossSiteRef(entity="Meeting", column="Log")]),
    )
    assert not any(f.severity == "error" and "site_role" in f.message for f in ok)


# === Retention cross-checks gated on bundle.retention_policies (Task 7) ===

def test_no_retention_config_no_retention_findings() -> None:
    """When no retention_policies_source is configured, mapping_loader loads
    retention_policies and retention_list_defaults as empty together — the
    retention cross-checks must be silent in that state."""
    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    bundle.retention_policies = {}
    bundle.retention_list_defaults = {}
    findings = validate_against_mapping(schema, bundle)
    assert not any("retention" in f.message.lower() for f in findings)


def test_retention_cross_checks_gated_on_policies_not_list_defaults() -> None:
    """Regression: the retention cross-checks must key off
    bundle.retention_policies being non-empty specifically, not off
    retention_list_defaults. A bundle with list_defaults but no policies
    (e.g. a malformed retention-policies.yaml) must not spuriously flag
    every list_defaults entry as 'not in policies' / 'unknown entity'."""
    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    assert bundle.retention_list_defaults  # fixture loads non-empty defaults
    bundle.retention_policies = {}
    findings = validate_against_mapping(schema, bundle)
    assert not any("retention" in f.message.lower() for f in findings)


# === validate_all + extension hook (Task 7) ===

class _StubExtension(BaseExtension):
    """Minimal extension stub: only extra_validators is overridden; every
    other hook keeps BaseExtension's no-op default."""

    name: ClassVar[str] = "stub"

    def extra_validators(self, bundle: Any, schema: Any) -> list[Finding]:
        return [Finding("warning", "stub extension finding")]


def test_validate_all_includes_extension_findings() -> None:
    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    findings = validate_all(schema, bundle, _StubExtension())
    assert any(f.message == "stub extension finding" for f in findings)


def test_validate_all_is_the_sum_of_its_parts() -> None:
    """validate_all(schema, bundle, extension) == validate(schema) +
    validate_against_mapping(schema, bundle) + extension.extra_validators
   , concatenated in that order."""
    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    extension = _StubExtension()
    findings = validate_all(schema, bundle, extension)
    expected = (
        validate(schema)
        + validate_against_mapping(schema, bundle)
        + extension.extra_validators(bundle, schema)
    )
    assert findings == expected


# --- Calculated columns (SP.FieldCalculated) --------------------------------


def _calc_inputs() -> tuple[Schema, MappingBundle]:
    schema = parse_dbml(FIXTURES / "calculated.dbml")
    bundle = load_mapping(FIXTURES / "calculated-mapping.yaml")
    return schema, bundle


def test_calculated_types_pass_schema_validation() -> None:
    table = Table(name="Risk", columns=[
        Column(name="Id", type="int", is_pk=True, is_auto_increment=True),
        Column(name="Score", type="calculated_number"),
        Column(name="Band", type="calculated_text"),
    ])
    findings = validate(_schema(table))
    assert not any("unknown type" in f.message for f in findings)


def test_valid_calculated_fixture_has_no_errors() -> None:
    schema, bundle = _calc_inputs()
    findings = validate(schema) + validate_against_mapping(schema, bundle)
    assert not any(f.severity == "error" for f in findings)


def test_calculated_column_without_formula_is_error() -> None:
    schema, bundle = _calc_inputs()
    del bundle.mapping.calculated_formulas["Risk"]["RiskScore"]
    findings = validate_against_mapping(schema, bundle)
    assert any(
        f.severity == "error" and "RiskScore" in f.message
        and "formula" in f.message.lower()
        for f in findings
    )


def test_orphan_calculated_formula_is_error() -> None:
    schema, bundle = _calc_inputs()
    bundle.mapping.calculated_formulas["Risk"]["NotAColumn"] = "=1"
    findings = validate_against_mapping(schema, bundle)
    assert any(
        f.severity == "error" and "NotAColumn" in f.message for f in findings
    )


def test_calculated_formula_must_start_with_equals() -> None:
    schema, bundle = _calc_inputs()
    bundle.mapping.calculated_formulas["Risk"]["RiskScore"] = 'IF([Severity]="High",10,1)'
    findings = validate_against_mapping(schema, bundle)
    assert any(
        f.severity == "error" and "RiskScore" in f.message and "'='" in f.message
        for f in findings
    )


def test_calculated_formula_over_sp_limit_is_error() -> None:
    schema, bundle = _calc_inputs()
    bundle.mapping.calculated_formulas["Risk"]["RiskScore"] = "=" + "1+" * 600 + "1"
    findings = validate_against_mapping(schema, bundle)
    assert any(
        f.severity == "error" and "1024" in f.message and "RiskScore" in f.message
        for f in findings
    )


def test_calculated_formula_unknown_column_reference_is_error() -> None:
    """SharePoint validates a formula's [Column] references when the field is
    created, so a reference that resolves to nothing fails the deployment with
    HTTP 500 ("The formula refers to a column that does not exist"). The build
    must fail closed instead of shipping the manifest with 0 findings."""
    schema, bundle = _calc_inputs()
    bundle.mapping.calculated_formulas["Risk"]["RiskScore"] = (
        '=IF([Severty]="High",10,1)'  # misspelled Severity
    )
    findings = validate_against_mapping(schema, bundle)
    assert any(
        f.severity == "error" and "RiskScore" in f.message and "Severty" in f.message
        for f in findings
    )
    # Bracket text inside string literals is NOT a column reference.
    bundle.mapping.calculated_formulas["Risk"]["RiskScore"] = (
        '=IF([Severity]="[Not A Column]",10,1)'
    )
    findings = validate_against_mapping(schema, bundle)
    assert not any("Not A Column" in f.message for f in findings)


def test_calculated_formula_self_reference_is_error() -> None:
    schema, bundle = _calc_inputs()
    bundle.mapping.calculated_formulas["Risk"]["RiskScore"] = "=[RiskScore]+1"
    findings = validate_against_mapping(schema, bundle)
    assert any(
        f.severity == "error" and "RiskScore" in f.message
        and "itself" in f.message
        for f in findings
    )


def test_calculated_formula_circular_references_are_error() -> None:
    schema, bundle = _calc_inputs()
    bundle.mapping.calculated_formulas["Risk"]["RiskScore"] = '=IF([RiskBand]="Red",10,1)'
    bundle.mapping.calculated_formulas["Risk"]["RiskBand"] = '=IF([RiskScore]>5,"Red","Green")'
    findings = validate_against_mapping(schema, bundle)
    assert any(
        f.severity == "error" and "circular" in f.message.lower()
        and "RiskBand" in f.message and "RiskScore" in f.message
        for f in findings
    )


def test_indexed_calculated_column_is_error() -> None:
    schema, bundle = _calc_inputs()
    bundle.mapping.indexed_columns["Risk"] = ["RiskScore"]
    findings = validate_against_mapping(schema, bundle)
    assert any(
        f.severity == "error" and "RiskScore" in f.message
        and "index" in f.message.lower() and "calculated" in f.message.lower()
        for f in findings
    )


# --- Declared views ---------------------------------------------------------


def _view_inputs(tmp_path: Path, views_block: str) -> tuple[Schema, MappingBundle]:
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Enum status {\n"
        '  "Open"\n'
        '  "Closed"\n'
        "}\n"
        "Table Project {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar [not null]\n"
        "  Status status\n"
        "  SortOrder int\n"
        "  DueDate date\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Project: { kind: List, base_template: 100, site_role: default }\n"
        + views_block,
        encoding="utf-8",
    )
    return parse_dbml(tmp_path / "s.dbml"), load_mapping(tmp_path / "m.yaml")


def _view_errors(tmp_path: Path, views_block: str) -> list[Finding]:
    schema, bundle = _view_inputs(tmp_path, views_block)
    return [f for f in validate_against_mapping(schema, bundle) if f.severity == "error"]


def test_view_on_unknown_entity_is_error(tmp_path: Path) -> None:
    errors = _view_errors(
        tmp_path,
        "views:\n  Widget:\n    - title: V\n      fields: [Title]\n",
    )
    assert any("Widget" in f.message and "views" in f.message for f in errors)


def test_view_field_references_must_be_rendered_columns(tmp_path: Path) -> None:
    errors = _view_errors(
        tmp_path,
        "views:\n"
        "  Project:\n"
        "    - title: V\n"
        "      fields: [Title, Nope]\n"
        "      where:\n"
        "        - { field: Missing, op: eq, value: x }\n"
        "      sort:\n"
        "        - { field: AlsoMissing, direction: asc }\n"
        "      group_by: { field: GoneToo }\n",
    )
    for name in ("Nope", "Missing", "AlsoMissing", "GoneToo"):
        assert any(name in f.message for f in errors), name


def test_view_operator_allowlist(tmp_path: Path) -> None:
    errors = _view_errors(
        tmp_path,
        "views:\n"
        "  Project:\n"
        "    - title: V\n"
        "      fields: [Title]\n"
        "      where:\n"
        "        - { field: Status, op: like, value: x }\n",
    )
    assert any("like" in f.message and "op" in f.message.lower() for f in errors)


def test_view_condition_value_pairing(tmp_path: Path) -> None:
    errors = _view_errors(
        tmp_path,
        "views:\n"
        "  Project:\n"
        "    - title: V\n"
        "      fields: [Title]\n"
        "      where:\n"
        "        - { field: Status, op: is_null, value: x }\n"
        "        - { field: SortOrder, op: eq }\n",
    )
    assert any("is_null" in f.message and "value" in f.message for f in errors)
    assert any("eq" in f.message and "value" in f.message for f in errors)


def test_view_widths_keys_must_be_view_fields(tmp_path: Path) -> None:
    # SortOrder IS a rendered column, but a width on a column the view does
    # not show is dead config — error, not silence.
    errors = _view_errors(
        tmp_path,
        "views:\n"
        "  Project:\n"
        "    - title: V\n"
        "      fields: [Title, Status]\n"
        "      widths:\n"
        "        Title: 240\n"
        "        SortOrder: 120\n",
    )
    assert any("widths" in f.message and "SortOrder" in f.message for f in errors)
    assert not any("widths" in f.message and "'Title'" in f.message for f in errors)


def test_view_widths_pixel_bounds(tmp_path: Path) -> None:
    errors = _view_errors(
        tmp_path,
        "views:\n"
        "  Project:\n"
        "    - title: V\n"
        "      fields: [Title, Status]\n"
        "      widths:\n"
        "        Title: 8\n"
        "        Status: 5000\n",
    )
    assert any("widths[Title]" in f.message and "16" in f.message for f in errors)
    assert any("widths[Status]" in f.message and "2000" in f.message for f in errors)


def test_demo_items_validated(tmp_path: Path) -> None:
    errors = _view_errors(
        tmp_path,
        "demo_items:\n"
        "  Project:\n"
        "    - key: p1\n"
        "      values:\n"
        '        Title: "Not marked"\n'          # missing [DEMO] prefix
        '        Status: "Sideways"\n'           # not an enum member
        "        Nope: 1\n"                      # unknown column
        '        DueDate: "someday"\n'           # bad date grammar
        "    - key: p1\n"                        # duplicate key
        "      values:\n"
        '        Title: "[DEMO] Ok"\n'
        "        SortOrder: { demo_ref: ghost }\n",
    )
    assert any("[DEMO] " in f.message and "Title" in f.message for f in errors)
    assert any("Sideways" in f.message and "status" in f.message for f in errors)
    assert any("Nope" in f.message and "writable" in f.message for f in errors)
    assert any("DueDate" in f.message and "today" in f.message for f in errors)
    assert any("duplicate demo key" in f.message for f in errors)
    assert any("ghost" in f.message for f in errors)


def test_demo_items_valid_set_passes(tmp_path: Path) -> None:
    errors = _view_errors(
        tmp_path,
        "demo_items:\n"
        "  Project:\n"
        "    - key: p1\n"
        "      values:\n"
        '        Title: "[DEMO] Sample"\n'
        '        Status: "Open"\n'
        "        SortOrder: 3\n"
        '        DueDate: "today+14"\n',
    )
    assert not any("demo_items" in f.message for f in errors)


def test_view_url_slug_collision_is_error(tmp_path: Path) -> None:
    # "A+B" and "A B" both slug to ABApsx — two views cannot share one URL.
    errors = _view_errors(
        tmp_path,
        "views:\n"
        "  Project:\n"
        "    - title: A+B\n"
        "      fields: [Title]\n"
        "    - title: A B\n"
        "      fields: [Title]\n",
    )
    assert any("slug" in f.message and "AB.aspx" in f.message for f in errors)


def test_view_url_slug_must_be_nonempty(tmp_path: Path) -> None:
    errors = _view_errors(
        tmp_path,
        "views:\n"
        "  Project:\n"
        "    - title: '!!!'\n"
        "      fields: [Title]\n",
    )
    assert any("slug" in f.message and "empty" in f.message for f in errors)


def test_view_today_sentinel_only_on_date_columns(tmp_path: Path) -> None:
    errors = _view_errors(
        tmp_path,
        "views:\n"
        "  Project:\n"
        "    - title: V\n"
        "      fields: [Title]\n"
        "      where:\n"
        "        - { field: SortOrder, op: leq, value: today+30 }\n",
    )
    assert any("today" in f.message and "SortOrder" in f.message for f in errors)
    ok = _view_errors(
        tmp_path,
        "views:\n"
        "  Project:\n"
        "    - title: V\n"
        "      fields: [Title]\n"
        "      where:\n"
        "        - { field: DueDate, op: leq, value: today+30 }\n",
    )
    assert ok == []


def test_view_titles_unique_and_single_default(tmp_path: Path) -> None:
    errors = _view_errors(
        tmp_path,
        "views:\n"
        "  Project:\n"
        "    - title: Same\n"
        "      default: true\n"
        "      fields: [Title]\n"
        "    - title: Same\n"
        "      default: true\n"
        "      fields: [Status]\n",
    )
    assert any("duplicate" in f.message.lower() for f in errors)
    assert any("default" in f.message.lower() for f in errors)


def test_view_row_limit_range(tmp_path: Path) -> None:
    errors = _view_errors(
        tmp_path,
        "views:\n"
        "  Project:\n"
        "    - title: V\n"
        "      fields: [Title]\n"
        "      row_limit: 9000\n",
    )
    assert any("row_limit" in f.message for f in errors)


# --- Display names ----------------------------------------------------------


def test_display_override_must_target_rendered_column(tmp_path: Path) -> None:
    errors = _view_errors(
        tmp_path,
        "display_names:\n"
        "  mode: auto\n"
        "  overrides:\n"
        "    Widget:\n"
        '      Anything: "X"\n'
        "    Project:\n"
        '      Nope: "Not A Column"\n',
    )
    assert any("Widget" in f.message and "display_names" in f.message for f in errors)
    assert any("Nope" in f.message and "display_names" in f.message for f in errors)


def test_display_names_must_be_unique_and_bounded(tmp_path: Path) -> None:
    errors = _view_errors(
        tmp_path,
        "display_names:\n"
        "  mode: auto\n"
        "  overrides:\n"
        "    Project:\n"
        '      Status: "Sort Order"\n'   # collides with auto(SortOrder)
        '      DueDate: ""\n',           # empty
    )
    assert any("Sort Order" in f.message and "duplicate" in f.message.lower() for f in errors)
    assert any("DueDate" in f.message and "empty" in f.message.lower() for f in errors)


# --- Column formatting ------------------------------------------------------


def test_formatter_field_refs_walks_nested_structures() -> None:
    from dbml_sharepoint.analysis.validator import formatter_field_refs

    refs = formatter_field_refs({
        "elmType": "div",
        "style": {"color": "=if([$Status] == 'Open', 'green', [$RiskScore])"},
        "children": [{"txtContent": "[$DueDate]"}, {"txtContent": "plain"}],
    })
    assert refs == frozenset({"Status", "RiskScore", "DueDate"})


def test_column_formatting_validation(tmp_path: Path) -> None:
    errors = _view_errors(
        tmp_path,
        "column_formatting:\n"
        "  Widget:\n"
        "    Anything: { elmType: div }\n"
        "  Project:\n"
        "    Nope: { elmType: div }\n"
        "    Status: { txtContent: x }\n"                     # no elmType
        "    SortOrder: { elmType: div, txtContent: '[$Missing]' }\n",
    )
    assert any("Widget" in f.message and "column_formatting" in f.message for f in errors)
    assert any("Nope" in f.message for f in errors)
    assert any("elmType" in f.message and "Status" in f.message for f in errors)
    assert any("Missing" in f.message and "SortOrder" in f.message for f in errors)
    ok = _view_errors(
        tmp_path,
        "column_formatting:\n"
        "  Project:\n"
        "    Status: { elmType: div, txtContent: '[$SortOrder]' }\n",
    )
    assert ok == []


def test_view_formatting_field_refs_validated(tmp_path: Path) -> None:
    errors = _view_errors(
        tmp_path,
        "views:\n"
        "  Project:\n"
        "    - title: V\n"
        "      fields: [Title]\n"
        "      formatting: { additionalRowClass: \"=if([$Ghost] == 1, 'x', '')\" }\n",
    )
    assert any("Ghost" in f.message and "V" in f.message for f in errors)


def test_form_formatting_validation(tmp_path: Path) -> None:
    errors = _view_errors(
        tmp_path,
        "form_formatting:\n"
        "  Widget:\n"
        "    header: { elmType: div }\n"
        "  Project:\n"
        "    header: { elmType: div, txtContent: '[$Ghost]' }\n"
        "    body: { sections: [ { displayname: X, fields: [Title, Nope] } ] }\n",
    )
    assert any("Widget" in f.message and "form_formatting" in f.message for f in errors)
    assert any("Ghost" in f.message for f in errors)
    assert any("Nope" in f.message and "sections" in f.message for f in errors)
    ok = _view_errors(
        tmp_path,
        "form_formatting:\n"
        "  Project:\n"
        "    body: { sections: [ { displayname: X, fields: [Title, Status] } ] }\n",
    )
    assert ok == []


def test_list_validation_rules_validated(tmp_path: Path) -> None:
    schema, bundle = _view_inputs(
        tmp_path,
        "list_validation:\n"
        "  Widget:\n"
        "    when:\n"
        "      - { field: Title, op: is_not_null }\n"
        "    message: x\n"
        "  Project:\n"
        "    when:\n"
        "      - { field: Ghost, op: eq, value: x }\n"
        "    message: x\n",
    )
    errors = [f for f in validate_against_mapping(schema, bundle) if f.severity == "error"]
    assert any("Widget" in f.message and "list_validation" in f.message for f in errors)
    assert any("Ghost" in f.message for f in errors)


def test_list_validation_rejects_unsupported_column_types(tmp_path: Path) -> None:
    """SP list validation formulas cannot reference calculated, person,
    lookup or multi-line columns — reject at build, not at paste."""
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Risk {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar [not null]\n"
        "  Score calculated_number\n"
        "  Owner person\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Risk: { kind: List, base_template: 100, site_role: default }\n"
        "calculated_formulas:\n"
        "  Risk:\n"
        "    Score: '=1'\n"
        "list_validation:\n"
        "  Risk:\n"
        "    when:\n"
        "      - { field: Score, op: gt, value: 0 }\n"
        "      - { field: Owner, op: is_not_null }\n"
        "    message: x\n",
        encoding="utf-8",
    )
    schema = parse_dbml(tmp_path / "s.dbml")
    bundle = load_mapping(tmp_path / "m.yaml")
    errors = [f for f in validate_against_mapping(schema, bundle) if f.severity == "error"]
    assert any("Score" in f.message and "calculated" in f.message.lower() for f in errors)
    assert any("Owner" in f.message and "person" in f.message.lower() for f in errors)




def test_today_offset_valid_on_calculated_date(tmp_path: Path) -> None:
    """A calculated_date column stores DateTime values — 'today' offset view
    filters must accept it (the NextReviewDue 'Reviews due' case)."""
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Risk {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar [not null]\n"
        "  NextReviewDue calculated_date\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Risk: { kind: List, base_template: 100, site_role: default }\n"
        "calculated_formulas:\n"
        "  Risk:\n"
        "    NextReviewDue: '=DATE(2026,1,1)'\n"
        "views:\n"
        "  Risk:\n"
        "    - title: Due\n"
        "      fields: [Title, NextReviewDue]\n"
        "      where:\n"
        "        - { field: NextReviewDue, op: leq, value: today+30 }\n",
        encoding="utf-8",
    )
    schema = parse_dbml(tmp_path / "s.dbml")
    bundle = load_mapping(tmp_path / "m.yaml")
    findings = validate_against_mapping(schema, bundle)
    assert not any(
        "offsets apply only" in f.message for f in findings if f.severity == "error"
    )


def test_watched_list_column_must_exist() -> None:
    """watched_lists is validated nowhere: a misspelled column simply
    never fires the status capture it was declared for."""
    from dbml_sharepoint.model.mapping_loader import WatchedList

    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    bundle.mapping.watched_lists = [WatchedList(entity="Task", column="NoSuchColumn")]
    findings = validate_against_mapping(schema, bundle)
    assert any(
        f.severity == "error" and "NoSuchColumn" in f.message and "watched_lists" in f.message
        for f in findings
    )


def test_polymorphic_pattern_columns_must_exist() -> None:
    """The manifest surfaces these so downstream flows validate the logical
    FK. A misspelled field or discriminator publishes a contract against a
    column that does not exist."""
    from dbml_sharepoint.model.mapping_loader import PolymorphicPattern

    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    bundle.mapping.polymorphic_patterns = [
        PolymorphicPattern(list="Task", field="NoSuchField", discriminator="NoSuchType"),
    ]
    findings = validate_against_mapping(schema, bundle)
    messages = [f.message for f in findings if f.severity == "error"]
    assert any("NoSuchField" in m and "polymorphic_patterns" in m for m in messages)
    assert any("NoSuchType" in m for m in messages)


def test_watched_list_entity_must_exist() -> None:
    from dbml_sharepoint.model.mapping_loader import WatchedList

    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    bundle.mapping.watched_lists = [WatchedList(entity="Tsak", column="Status")]
    findings = validate_against_mapping(schema, bundle)
    assert any(
        f.severity == "error" and "Tsak" in f.message and "watched_lists" in f.message
        for f in findings
    )


def test_polymorphic_pattern_entity_must_exist() -> None:
    from dbml_sharepoint.model.mapping_loader import PolymorphicPattern

    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    bundle.mapping.polymorphic_patterns = [
        PolymorphicPattern(list="Tsak", field="Status", discriminator="Status"),
    ]
    findings = validate_against_mapping(schema, bundle)
    assert any(
        f.severity == "error" and "Tsak" in f.message and "polymorphic_patterns" in f.message
        for f in findings
    )


def test_versioning_override_entity_must_exist() -> None:
    """A misspelled entity under `versioning.overrides` leaves the real
    list on the defaults — versioning ON when the author turned it off —
    and nothing reads the orphan block, so nothing reported it."""
    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    bundle.mapping.versioning_overrides["Tsak"] = {"enable_versioning": False}
    findings = validate_against_mapping(schema, bundle)
    assert any(
        f.severity == "error" and "Tsak" in f.message and "versioning" in f.message
        for f in findings
    )


def test_auto_increment_column_not_named_id_is_rejected() -> None:
    """typemap skips any `int [pk, increment]` column, while jsgen and the
    rendered-column oracle special-case the NAME "Id". So `TicketId int
    [pk, increment]` was validated as a real column and never created, and
    every consequence validated clean: form_visibility, column_validation
    and column_formatting deployed nothing; indexed_columns and
    views.fields emitted calls that 400 live; demo_items wrote to a column
    that does not exist."""
    table = Table(name="Ticket", columns=[
        Column(name="TicketId", type="int", is_pk=True, is_auto_increment=True),
        Column(name="Title", type="nvarchar", required=True),
    ])
    findings = validate(_schema(table))
    assert any(
        f.severity == "error" and "TicketId" in f.message and "Id" in f.message
        for f in findings
    ), findings


def test_auto_increment_column_named_id_is_accepted() -> None:
    table = Table(name="Ticket", columns=[
        Column(name="Id", type="int", is_pk=True, is_auto_increment=True),
        Column(name="Title", type="nvarchar", required=True),
    ])
    assert [f for f in validate(_schema(table)) if f.severity == "error"] == []


def test_column_named_id_that_is_not_the_identity_is_rejected() -> None:
    """The inverse: SharePoint reserves ID on every list, so a plain
    `Id nvarchar` was emitted as a Text field against a name that already
    exists. RESERVED_NAMES omitted it."""
    table = Table(name="Ticket", columns=[
        Column(name="Id", type="nvarchar"),
        Column(name="Title", type="nvarchar", required=True),
    ])
    findings = validate(_schema(table))
    assert any(
        f.severity == "error" and "Id" in f.message for f in findings
    ), findings
