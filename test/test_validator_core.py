"""Validator: the shared fixtures, cross-cutting checks and the extension hook."""
from pathlib import Path
from typing import Any, ClassVar

import pytest
from _builders import ID_PK, TITLE, table
from _packs import blocks, entities, pack, write_dbml, write_mapping
from _paths import FIXTURES
from _validator_helpers import _schema

from dbml_sharepoint.analysis.findings import FindingCode
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
from dbml_sharepoint.model.parser import (
    Column,
    EnumDef,
    Reference,
    Table,
    parse_dbml,
)


def test_style_map_keys_must_be_enum_members(tmp_path: Path) -> None:
    """A severity/pill map naming a choice the column's enum does not
    contain is a declaration bug — same ethos as [$Field] checking."""
    schema, bundle = pack(
        tmp_path,
        dbml=blocks(
            """
            Enum status {
              "Open"
              "Closed"
            }
            """,
            table("Risk", ID_PK, TITLE, "Status status"),
        ),
        mapping=blocks(entities("Risk"), """
            column_formatting:
              Risk:
                Status: { style: severity, map: { Open: low, Bogus: good } }
        """),
    )
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
    schema, bundle = pack(
        tmp_path,
        dbml=blocks(
            """
            Enum rating {
              "Low"
              "High"
            }
            """,
            table("Risk", ID_PK, TITLE, "Rating rating", "Score int"),
        ),
        mapping=blocks(entities("Risk"), """
            column_formatting:
              Risk:
                Score: { style: data-bar, max: 25,
                         color_by: { field: Rating, map: { Low: good, Bogus: blocked } } }
        """),
    )
    findings = validate_against_mapping(schema, bundle)
    assert any(
        "Bogus" in f.message and "column_formatting[Risk].Score" in f.message
        for f in findings if f.severity == "error"
    )
    # The valid key raises nothing.
    assert not any("'Low'" in f.message for f in findings if f.severity == "error")

def test_calculated_number_and_date_styles_require_decoding(tmp_path: Path) -> None:
    schema, bundle = pack(
        tmp_path,
        dbml=table("Risk", ID_PK, "Score calculated_number", "Due calculated_date"),
        mapping=blocks(entities("Risk"), """
            calculated_formulas:
              Risk:
                Score: '=1'
                Due: '=DATE(2026,1,1)'
            column_formatting:
              Risk:
                Score: { style: data-bar, max: 25 }
                Due: { style: overdue-date }
        """),
    )
    findings = validate_against_mapping(schema, bundle)
    errors = [f.message for f in findings if f.severity == "error"]
    assert any("Score" in message and "calculated: true" in message for message in errors)
    assert any("Due" in message and "calculated: true" in message for message in errors)

def test_formatter_may_reference_system_columns(tmp_path: Path) -> None:
    """[$Created]/[$Modified]/[$ID]/[$Author]/[$Editor] always exist on a
    list; formatter references to them must not be rejected, while a
    genuinely unknown reference still errors."""
    schema, bundle = pack(
        tmp_path,
        dbml=table("Risk", ID_PK, TITLE, "Gap int"),
        mapping=blocks(entities("Risk"), """
            column_formatting:
              Risk:
                Gap:
                  elmType: div
                  txtContent: "=toLocaleDateString([$Created] + 1)"
        """),
    )
    findings = validate_against_mapping(schema, bundle)
    assert not any("Created" in f.message for f in findings if f.severity == "error")
    unknown_ref = write_mapping(
        tmp_path,
        blocks(entities("Risk"), """
            column_formatting:
              Risk:
                Gap:
                  elmType: div
                  txtContent: "=[$Nope]"
        """),
        name="m2.yaml",
    )
    findings2 = validate_against_mapping(schema, load_mapping(unknown_ref))
    assert any("Nope" in f.message for f in findings2 if f.severity == "error")

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

@pytest.mark.parametrize(
    "column_type",
    [
        "longtext",
        "richtext",
        "hyperlink",
        "boolean",
        "calculated_text",
        "calculated_number",
        "calculated_date",
    ],
)
def test_unique_is_rejected_for_unsupported_sharepoint_types(
    column_type: str,
) -> None:
    table = Table(name="Record", columns=[
        Column(name="Id", type="int", is_pk=True, is_auto_increment=True),
        Column(name="Value", type=column_type, unique=True),
    ])

    findings = validate(_schema(table))

    assert any(
        finding.severity == "error"
        and "Value" in finding.message
        and "unique" in finding.message
        and "not supported" in finding.message
        for finding in findings
    )

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

def test_indexed_column_cross_site_logical_name_is_error(tmp_path: Path) -> None:
    """A cross-site column's logical DBML field is expanded and never exists
    in SharePoint, so its otherwise-valid DBML index must be rejected."""
    schema, bundle = pack(
        tmp_path,
        dbml=blocks(
            table("Project", ID_PK, "Title nvarchar"),
            table("Task", ID_PK, "Project int [ref: > Project.Id]", "indexes { Project }"),
        ),
        mapping=blocks(entities("Project", "Task"), """
            cross_site_reference_columns:
              - { entity: Task, column: Project }
        """),
    )
    findings = validate_against_mapping(schema, bundle)
    assert any(
        f.severity == "error"
        and "Project" in f.message
        and "indexes" in f.message
        for f in findings
    )

def test_dbml_indexes_reject_unsupported_field_types(tmp_path: Path) -> None:
    schema, bundle = pack(
        tmp_path,
        dbml="""
            Table Task {
              Id int [pk, increment]
              Notes longtext
              Url hyperlink
              indexes {
                Notes
                Url
              }
            }
        """,
        mapping=entities("Task"),
    )
    findings = validate_against_mapping(schema, bundle)
    assert any(
        f.severity == "error" and "Notes" in f.message and "Note" in f.message
        for f in findings
    )
    assert any(
        f.severity == "error" and "Url" in f.message and "Hyperlink" in f.message
        for f in findings
    )

def test_dbml_indexes_reject_duplicates_and_more_than_twenty(tmp_path: Path) -> None:
    # Col0 is listed twice on purpose -- that is the duplicate this asserts.
    index_lines = [f"    Col{i}" for i in range(21)] + ["    Col0"]
    write_dbml(tmp_path, table(
        "Wide",
        ID_PK,
        *(f"Col{i} nvarchar" for i in range(21)),
        "indexes {\n" + "\n".join(index_lines) + "\n  }",
    ))
    mapping = write_mapping(tmp_path, entities("Wide"))
    findings = validate_against_mapping(
        parse_dbml(tmp_path / "s.dbml"), load_mapping(mapping),
    )
    assert any(
        f.severity == "error" and "Col0" in f.message and "duplicate" in f.message
        for f in findings
    )
    assert any(
        f.severity == "error" and "21" in f.message and "20" in f.message
        for f in findings
    )

def test_unique_columns_count_toward_index_limit_without_mapping_entry(tmp_path: Path) -> None:
    write_dbml(tmp_path, table(
        "Wide", ID_PK, *(f"Col{i} nvarchar [unique]" for i in range(21)),
    ))
    mapping = write_mapping(tmp_path, entities("Wide"))
    findings = validate_against_mapping(
        parse_dbml(tmp_path / "s.dbml"), load_mapping(mapping),
    )
    assert any(
        f.severity == "error" and "21" in f.message and "20" in f.message
        for f in findings
    )

def test_dbml_index_must_not_repeat_a_unique_column(tmp_path: Path) -> None:
    schema, bundle = pack(
        tmp_path,
        dbml=table("Asset", ID_PK, "AssetTag nvarchar [unique]", "indexes { AssetTag }"),
        mapping=entities("Asset"),
    )
    findings = validate_against_mapping(schema, bundle)
    assert any(
        finding.severity == "error"
        and "AssetTag" in finding.message
        and "unique" in finding.message
        and "indexes" in finding.message
        for finding in findings
    )

def test_index_headroom_warns_at_eighteen(tmp_path: Path) -> None:
    """The budget cannot be counted exactly: SharePoint creates indexes itself.
    Opening a modern view sorted on an unindexed column produced
    "SortBait (Automatically created)", which consumes a real slot, and nothing
    reachable from script reports the true count. So a schema that validates at
    exactly 20 can still hit 21 on a tenant where a user has sorted a column."""
    indexed = [f"C{i}" for i in range(1, 19)]
    write_dbml(tmp_path, table(
        "Big",
        ID_PK,
        *(f"{c} nvarchar" for c in indexed),
        "indexes { " + " ".join(indexed) + " }",
    ))
    mapping = write_mapping(tmp_path, entities("Big"))
    warnings = [
        f.message
        for f in validate_against_mapping(
            parse_dbml(tmp_path / "s.dbml"), load_mapping(mapping),
        )
        if f.severity == "warning" and "18 of the 20" in f.message
    ]
    assert len(warnings) == 1
    assert "sorted view" in warnings[0]

def test_index_headroom_no_warning_at_seventeen(tmp_path: Path) -> None:
    """The budget cannot be counted exactly: SharePoint creates indexes itself.
    Opening a modern view sorted on an unindexed column produced
    "SortBait (Automatically created)", which consumes a real slot, and nothing
    reachable from script reports the true count. So a schema that validates at
    exactly 20 can still hit 21 on a tenant where a user has sorted a column."""
    indexed = [f"C{i}" for i in range(1, 18)]
    write_dbml(tmp_path, table(
        "Big",
        ID_PK,
        *(f"{c} nvarchar" for c in indexed),
        "indexes { " + " ".join(indexed) + " }",
    ))
    mapping = write_mapping(tmp_path, entities("Big"))
    warnings = [
        f.message
        for f in validate_against_mapping(
            parse_dbml(tmp_path / "s.dbml"), load_mapping(mapping),
        )
        if f.severity == "warning" and "18 of the 20" in f.message
    ]
    assert warnings == []

def test_index_error_at_twentyone_excludes_headroom_warning(tmp_path: Path) -> None:
    """The error firing at > 20 means the warning is unreachable at that threshold.
    This test pins the mutual exclusion: at 21 the author needs the error, and a
    headroom warning beside it would be noise about a list that is already over."""
    indexed = [f"C{i}" for i in range(1, 22)]
    write_dbml(tmp_path, table(
        "Big",
        ID_PK,
        *(f"{c} nvarchar" for c in indexed),
        "indexes { " + " ".join(indexed) + " }",
    ))
    mapping = write_mapping(tmp_path, entities("Big"))
    findings = validate_against_mapping(
        parse_dbml(tmp_path / "s.dbml"), load_mapping(mapping),
    )
    errors = [
        f.message
        for f in findings
        if f.severity == "error" and "exceed SharePoint's limit of 20" in f.message
    ]
    warnings = [
        f.message
        for f in findings
        if f.severity == "warning" and "available indexes are already spoken for" in f.message
    ]
    assert len(errors) == 1
    assert len(warnings) == 0

def test_twenty_declared_on_a_lookup_target_names_the_twentyfirst(
    tmp_path: Path,
) -> None:
    """The case this whole rule exists for. The author declared twenty, has no
    unique columns, and the only hint used to be "(including unique columns)" —
    which is false here. The error must name the display column as the index
    they cannot see."""
    columns = "\n".join(f"  C{i} nvarchar" for i in range(1, 21))
    indexes = " ".join(f"C{i}" for i in range(1, 21))
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        f"Table Event {{\n  Id int [pk, increment]\n  Title nvarchar\n{columns}\n"
        f"  indexes {{ {indexes} }}\n}}\n"
        "Table FollowUp {\n"
        "  Id int [pk, increment]\n"
        "  Event int [ref: > Event.Id]\n"
        "}\n",
        encoding="utf-8",
    )
    mapping = write_mapping(tmp_path, entities("Event", "FollowUp"))
    errors = [
        f.message
        for f in validate_against_mapping(
            parse_dbml(tmp_path / "s.dbml"), load_mapping(mapping),
        )
        if f.severity == "error" and "exceed SharePoint's limit of 20" in f.message
    ]
    assert len(errors) == 1, errors
    assert "21 " in errors[0]
    assert "20 declared in indexes" in errors[0]
    assert "'Title'" in errors[0]
    assert "lookup target" in errors[0]
    # The old parenthetical claimed unique columns were in the count. There are
    # none on this list, so it must not say so.
    assert "unique" not in errors[0]

def test_the_over_budget_error_names_unique_columns_when_there_are_some(
    tmp_path: Path,
) -> None:
    """The other implicit contributor. Naming one and not the other would send
    an author looking in the wrong place."""
    indexed = [f"C{i}" for i in range(1, 21)]
    write_dbml(tmp_path, table(
        "Big",
        ID_PK,
        "Code nvarchar [unique]",
        *(f"{c} nvarchar" for c in indexed),
        "indexes { " + " ".join(indexed) + " }",
    ))
    mapping = write_mapping(tmp_path, entities("Big"))
    errors = [
        f.message
        for f in validate_against_mapping(
            parse_dbml(tmp_path / "s.dbml"), load_mapping(mapping),
        )
        if f.severity == "error" and "exceed SharePoint's limit of 20" in f.message
    ]
    assert len(errors) == 1, errors
    assert "'Code' from a [unique] column" in errors[0]
    # Nothing looks Big up, so there is no display-column index to blame.
    assert "lookup target" not in errors[0]

def test_dbml_composite_and_configured_indexes_are_rejected(tmp_path: Path) -> None:
    schema, bundle = pack(
        tmp_path,
        dbml="""
            Table Risk {
              Id int [pk, increment]
              Status nvarchar
              Category nvarchar
              indexes {
                (Status, Category)
                Status [name: 'status_index']
              }
            }
        """,
        mapping=entities("Risk"),
    )
    findings = validate_against_mapping(schema, bundle)
    errors = [f.message for f in findings if f.severity == "error"]
    assert any("composite" in message for message in errors)
    assert any("name" in message and "status_index" in message for message in errors)

def test_cross_site_reference_cannot_declare_unique_constraint(tmp_path: Path) -> None:
    schema, bundle = pack(
        tmp_path,
        dbml=blocks(
            table("Project", ID_PK, "Title nvarchar"),
            table("Task", ID_PK, "Project int [unique, ref: > Project.Id]"),
        ),
        mapping=blocks(entities("Project", "Task"), """
            cross_site_reference_columns:
              - { entity: Task, column: Project }
        """),
    )
    findings = validate_against_mapping(schema, bundle)
    assert any(
        finding.severity == "error"
        and "Task.Project" in finding.message
        and "unique" in finding.message
        and "cross-site" in finding.message
        for finding in findings
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
            cross_site_reference_columns=[],
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
            cross_site_reference_columns=[],
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
            cross_site_reference_columns=cross_site,
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
        return [Finding(FindingCode.EXTENSION_REPORTED, "warning", "stub extension finding")]

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
