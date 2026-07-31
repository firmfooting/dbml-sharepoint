# test/test_validator.py
import ast
from pathlib import Path
from typing import Any, ClassVar

import pytest

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
    Schema,
    Table,
    TableIndex,
    parse_dbml,
)


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


def test_calculated_number_and_date_styles_require_decoding(tmp_path: Path) -> None:
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Risk {\n"
        "  Id int [pk, increment]\n"
        "  Score calculated_number\n"
        "  Due calculated_date\n"
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
        "    Due: '=DATE(2026,1,1)'\n"
        "column_formatting:\n"
        "  Risk:\n"
        "    Score: { style: data-bar, max: 25 }\n"
        "    Due: { style: overdue-date }\n",
        encoding="utf-8",
    )
    findings = validate_against_mapping(
        parse_dbml(tmp_path / "s.dbml"), load_mapping(tmp_path / "m.yaml"),
    )
    errors = [f.message for f in findings if f.severity == "error"]
    assert any("Score" in message and "calculated: true" in message for message in errors)
    assert any("Due" in message and "calculated: true" in message for message in errors)


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


def _bundle_with_formulas(
    formulas: dict[str, dict[str, str]], *entity_names: str,
) -> MappingBundle:
    """A minimal bundle declaring the named entities plus calculated formulas."""
    mapping = Mapping(
        prefix="APP_", prefix_owner="", prefix_registry="",
        entities={
            name: EntityMapping(
                name=name, kind="List", base_template=100, site_role="default",
            )
            for name in entity_names
        },
        cross_site_reference_columns=[],
        versioning_default=Versioning(True, 500, False), versioning_overrides={},
        enum_sources={}, watched_lists=[], calculated_formulas=formulas,
    )
    return MappingBundle(
        mapping=mapping, enum_choices={}, retention_policies={},
        retention_list_defaults={},
    )


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
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Project {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar\n"
        "}\n"
        "Table Task {\n"
        "  Id int [pk, increment]\n"
        "  Project int [ref: > Project.Id]\n"
        "  indexes { Project }\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Project: { kind: List, base_template: 100, site_role: default }\n"
        "  Task: { kind: List, base_template: 100, site_role: default }\n"
        "cross_site_reference_columns:\n"
        "  - { entity: Task, column: Project }\n",
        encoding="utf-8",
    )
    findings = validate_against_mapping(
        parse_dbml(tmp_path / "s.dbml"), load_mapping(tmp_path / "m.yaml"),
    )
    assert any(
        f.severity == "error"
        and "Project" in f.message
        and "indexes" in f.message
        for f in findings
    )


def test_dbml_indexes_reject_unsupported_field_types(tmp_path: Path) -> None:
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Task {\n"
        "  Id int [pk, increment]\n"
        "  Notes longtext\n"
        "  Url hyperlink\n"
        "  indexes {\n"
        "    Notes\n"
        "    Url\n"
        "  }\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Task: { kind: List, base_template: 100, site_role: default }\n",
        encoding="utf-8",
    )
    findings = validate_against_mapping(
        parse_dbml(tmp_path / "s.dbml"), load_mapping(tmp_path / "m.yaml"),
    )
    assert any(
        f.severity == "error" and "Notes" in f.message and "Note" in f.message
        for f in findings
    )
    assert any(
        f.severity == "error" and "Url" in f.message and "Hyperlink" in f.message
        for f in findings
    )


def test_dbml_indexes_reject_duplicates_and_more_than_twenty(tmp_path: Path) -> None:
    columns = "".join(f"  Col{i} nvarchar\n" for i in range(21))
    indexes = "".join(f"    Col{i}\n" for i in range(21)) + "    Col0\n"
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        f"Table Wide {{\n  Id int [pk, increment]\n{columns}"
        f"  indexes {{\n{indexes}  }}\n}}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Wide: { kind: List, base_template: 100, site_role: default }\n",
        encoding="utf-8",
    )
    findings = validate_against_mapping(
        parse_dbml(tmp_path / "s.dbml"), load_mapping(tmp_path / "m.yaml"),
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
    columns = "".join(f"  Col{i} nvarchar [unique]\n" for i in range(21))
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        f"Table Wide {{\n  Id int [pk, increment]\n{columns}}}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Wide: { kind: List, base_template: 100, site_role: default }\n",
        encoding="utf-8",
    )
    findings = validate_against_mapping(
        parse_dbml(tmp_path / "s.dbml"), load_mapping(tmp_path / "m.yaml"),
    )
    assert any(
        f.severity == "error" and "21" in f.message and "20" in f.message
        for f in findings
    )


def test_dbml_index_must_not_repeat_a_unique_column(tmp_path: Path) -> None:
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Asset {\n"
        "  Id int [pk, increment]\n"
        "  AssetTag nvarchar [unique]\n"
        "  indexes { AssetTag }\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Asset: { kind: List, base_template: 100, site_role: default }\n",
        encoding="utf-8",
    )
    findings = validate_against_mapping(
        parse_dbml(tmp_path / "s.dbml"), load_mapping(tmp_path / "m.yaml"),
    )
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
    columns = "\n".join(f"  C{i} nvarchar" for i in range(1, 19))
    indexes = " ".join(f"C{i}" for i in range(1, 19))
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        f"Table Big {{\n  Id int [pk, increment]\n{columns}\n"
        f"  indexes {{ {indexes} }}\n}}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Big: { kind: List, base_template: 100, site_role: default }\n",
        encoding="utf-8",
    )
    warnings = [
        f.message
        for f in validate_against_mapping(
            parse_dbml(tmp_path / "s.dbml"), load_mapping(tmp_path / "m.yaml"),
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
    columns = "\n".join(f"  C{i} nvarchar" for i in range(1, 18))
    indexes = " ".join(f"C{i}" for i in range(1, 18))
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        f"Table Big {{\n  Id int [pk, increment]\n{columns}\n"
        f"  indexes {{ {indexes} }}\n}}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Big: { kind: List, base_template: 100, site_role: default }\n",
        encoding="utf-8",
    )
    warnings = [
        f.message
        for f in validate_against_mapping(
            parse_dbml(tmp_path / "s.dbml"), load_mapping(tmp_path / "m.yaml"),
        )
        if f.severity == "warning" and "18 of the 20" in f.message
    ]
    assert warnings == []


def test_index_error_at_twentyone_excludes_headroom_warning(tmp_path: Path) -> None:
    """The error firing at > 20 means the warning is unreachable at that threshold.
    This test pins the mutual exclusion: at 21 the author needs the error, and a
    headroom warning beside it would be noise about a list that is already over."""
    columns = "\n".join(f"  C{i} nvarchar" for i in range(1, 22))
    indexes = " ".join(f"C{i}" for i in range(1, 22))
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        f"Table Big {{\n  Id int [pk, increment]\n{columns}\n"
        f"  indexes {{ {indexes} }}\n}}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Big: { kind: List, base_template: 100, site_role: default }\n",
        encoding="utf-8",
    )
    findings = validate_against_mapping(
        parse_dbml(tmp_path / "s.dbml"), load_mapping(tmp_path / "m.yaml"),
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
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Event: { kind: List, base_template: 100, site_role: default }\n"
        "  FollowUp: { kind: List, base_template: 100, site_role: default }\n",
        encoding="utf-8",
    )
    errors = [
        f.message
        for f in validate_against_mapping(
            parse_dbml(tmp_path / "s.dbml"), load_mapping(tmp_path / "m.yaml"),
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
    columns = "\n".join(f"  C{i} nvarchar" for i in range(1, 21))
    indexes = " ".join(f"C{i}" for i in range(1, 21))
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        f"Table Big {{\n  Id int [pk, increment]\n  Code nvarchar [unique]\n{columns}\n"
        f"  indexes {{ {indexes} }}\n}}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Big: { kind: List, base_template: 100, site_role: default }\n",
        encoding="utf-8",
    )
    errors = [
        f.message
        for f in validate_against_mapping(
            parse_dbml(tmp_path / "s.dbml"), load_mapping(tmp_path / "m.yaml"),
        )
        if f.severity == "error" and "exceed SharePoint's limit of 20" in f.message
    ]
    assert len(errors) == 1, errors
    assert "'Code' from a [unique] column" in errors[0]
    # Nothing looks Big up, so there is no display-column index to blame.
    assert "lookup target" not in errors[0]


def test_dbml_composite_and_configured_indexes_are_rejected(tmp_path: Path) -> None:
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Risk {\n"
        "  Id int [pk, increment]\n"
        "  Status nvarchar\n"
        "  Category nvarchar\n"
        "  indexes {\n"
        "    (Status, Category)\n"
        "    Status [name: 'status_index']\n"
        "  }\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Risk: { kind: List, base_template: 100, site_role: default }\n",
        encoding="utf-8",
    )
    findings = validate_against_mapping(
        parse_dbml(tmp_path / "s.dbml"), load_mapping(tmp_path / "m.yaml"),
    )
    errors = [f.message for f in findings if f.severity == "error"]
    assert any("composite" in message for message in errors)
    assert any("name" in message and "status_index" in message for message in errors)


def test_cross_site_reference_cannot_declare_unique_constraint(tmp_path: Path) -> None:
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Project {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar\n"
        "}\n"
        "Table Task {\n"
        "  Id int [pk, increment]\n"
        "  Project int [unique, ref: > Project.Id]\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Project: { kind: List, base_template: 100, site_role: default }\n"
        "  Task: { kind: List, base_template: 100, site_role: default }\n"
        "cross_site_reference_columns:\n"
        "  - { entity: Task, column: Project }\n",
        encoding="utf-8",
    )
    findings = validate_against_mapping(
        parse_dbml(tmp_path / "s.dbml"), load_mapping(tmp_path / "m.yaml"),
    )
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


def test_calculated_formula_lookup_operand_is_error() -> None:
    parent = Table(name="Risk", columns=[
        Column(name="Id", type="int", is_pk=True, is_auto_increment=True),
        Column(name="Title", type="nvarchar", required=True),
    ])
    child = Table(name="Action", columns=[
        Column(name="Id", type="int", is_pk=True, is_auto_increment=True),
        Column(name="Title", type="nvarchar", required=True),
        Column(name="Risk", type="int", ref=Reference("Risk", "Id")),
        Column(name="RiskCopy", type="calculated_text"),
    ])
    bundle = _bundle_with_formulas(
        {"Action": {"RiskCopy": "=[Risk]"}},
        "Risk",
        "Action",
    )
    errors = [
        finding
        for finding in validate_against_mapping(_schema(parent, child), bundle)
        if finding.severity == "error"
    ]
    message = next(
        finding.message
        for finding in errors
        if "Action.RiskCopy" in finding.message and "[Risk]" in finding.message
    )
    assert "Lookup" in message
    assert "HTTP 500" in message
    assert "not supported in formulas" in message
    # Naming the supported set matters more than naming the excluded one: an
    # author who reads "not a Lookup" still has to guess what IS allowed.
    assert "Yes/No" in message


def test_calculated_formula_person_operand_is_error() -> None:
    table = Table(name="Risk", columns=[
        Column(name="Id", type="int", is_pk=True, is_auto_increment=True),
        Column(name="Title", type="nvarchar", required=True),
        Column(name="Owner", type="person"),
        Column(name="OwnerCopy", type="calculated_text"),
    ])
    bundle = _bundle_with_formulas(
        {"Risk": {"OwnerCopy": "=[Owner]"}},
        "Risk",
    )
    errors = [
        finding
        for finding in validate_against_mapping(_schema(table), bundle)
        if finding.severity == "error"
    ]
    message = next(
        finding.message
        for finding in errors
        if "Risk.OwnerCopy" in finding.message and "[Owner]" in finding.message
    )
    assert "Person" in message
    assert "HTTP 500" in message
    assert "not supported in formulas" in message
    assert "Yes/No" in message


@pytest.mark.parametrize(
    ("operand_type", "described_as"),
    [
        ("longtext", "plain multi-line-text"),
        ("richtext", "rich-text"),
        ("hyperlink", "Hyperlink"),
    ],
)
def test_probed_calculated_operand_types_are_errors(
    operand_type: str, described_as: str,
) -> None:
    """These three were held OUT of the denylist while unverified, because
    Microsoft's silence about a type is not evidence against it.
    test/manual/calculated-operand-probe.js was run live on 2026-07-30 and
    refused all three with HTTP 500 and the same "not supported in formulas"
    body as Lookup and Person, so they belong in it now.
    """
    table = Table(name="Risk", columns=[
        Column(name="Id", type="int", is_pk=True, is_auto_increment=True),
        Column(name="Title", type="nvarchar", required=True),
        Column(name="Source", type=operand_type),
        Column(name="Copy", type="calculated_text"),
    ])
    bundle = _bundle_with_formulas({"Risk": {"Copy": "=[Source]"}}, "Risk")
    message = next(
        finding.message
        for finding in validate_against_mapping(_schema(table), bundle)
        if finding.severity == "error" and "[Source]" in finding.message
    )
    assert "Risk.Copy" in message
    assert described_as in message
    assert "not supported in formulas" in message


@pytest.mark.parametrize("operand_type", ["nvarchar", "number", "boolean", "datetime"])
def test_probe_accepted_calculated_operand_types_stay_allowed(operand_type: str) -> None:
    """The other half of the same live run, and the reason the denylist is a
    denylist. Yes/No in particular was never refused — a probe-free guess that
    "SharePoint only does text and numbers in formulas" would have banned it.
    """
    table = Table(name="Risk", columns=[
        Column(name="Id", type="int", is_pk=True, is_auto_increment=True),
        Column(name="Title", type="nvarchar", required=True),
        Column(name="Source", type=operand_type),
        Column(name="Copy", type="calculated_text"),
    ])
    bundle = _bundle_with_formulas({"Risk": {"Copy": "=[Source]"}}, "Risk")
    errors = [
        finding
        for finding in validate_against_mapping(_schema(table), bundle)
        if finding.severity == "error"
    ]
    assert not any("[Source]" in finding.message for finding in errors), errors


def test_calculated_formula_cross_site_text_companion_is_allowed() -> None:
    unit = Table(name="Unit", columns=[
        Column(name="Id", type="int", is_pk=True, is_auto_increment=True),
        Column(name="Title", type="nvarchar", required=True),
    ])
    project = Table(name="Project", columns=[
        Column(name="Id", type="int", is_pk=True, is_auto_increment=True),
        Column(name="Title", type="nvarchar", required=True),
        Column(name="Unit", type="int", ref=Reference("Unit", "Id")),
        Column(name="UnitLabel", type="calculated_text"),
    ])
    bundle = _bundle_with_formulas(
        {"Project": {"UnitLabel": "=[UnitAbbreviation]"}},
        "Unit",
        "Project",
    )
    bundle.mapping.cross_site_reference_columns.append(
        CrossSiteRef(entity="Project", column="Unit"),
    )
    errors = [
        finding
        for finding in validate_against_mapping(_schema(unit, project), bundle)
        if finding.severity == "error"
    ]
    assert not any("UnitAbbreviation" in finding.message for finding in errors), errors


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
    next(table for table in schema.tables if table.name == "Risk").indexes.append(
        TableIndex(("RiskScore",)),
    )
    findings = validate_against_mapping(schema, bundle)
    assert any(
        f.severity == "error" and "RiskScore" in f.message
        and "index" in f.message.lower() and "calculated" in f.message.lower()
        for f in findings
    )


# --- Lookup target's display column must be indexable -----------------------


def _calculated_display_inputs(
    tmp_path: Path, *, accepted: bool,
) -> tuple[Schema, MappingBundle]:
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Event {\n"
        "  Id int [pk, increment]\n"
        "  Ref nvarchar\n"
        "  Label calculated_text\n"
        "}\n"
        "Table FollowUp {\n"
        "  Id int [pk, increment]\n"
        "  Event int [ref: > Event.Id]\n"
        "}\n",
        encoding="utf-8",
    )
    accept = ", accept_unindexable_display_column: true" if accepted else ""
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Event: { kind: List, base_template: 100, site_role: default, "
        f"display_column: Label{accept} }}\n"
        "  FollowUp: { kind: List, base_template: 100, site_role: default }\n",
        encoding="utf-8",
    )
    return parse_dbml(tmp_path / "s.dbml"), load_mapping(tmp_path / "m.yaml")


def test_a_calculated_display_column_warns_about_the_form(tmp_path: Path) -> None:
    """A warning, not an error: a target that stays under 5,000 has no problem.
    But the message must say the FORM breaks — "cannot be indexed" does not tell
    an author what their users will see."""
    schema, bundle = _calculated_display_inputs(tmp_path, accepted=False)
    warnings = [
        f.message
        for f in validate_against_mapping(schema, bundle)
        if f.severity == "warning" and "display_column" in f.message
    ]
    assert len(warnings) == 1
    assert "Label" in warnings[0]
    assert "new-item form" in warnings[0]
    assert "5,000" in warnings[0]
    assert "accept_unindexable_display_column" in warnings[0]
    # Not an error: a small list is a legitimate case.
    assert not [
        f for f in validate_against_mapping(schema, bundle)
        if f.severity == "error" and "display_column" in f.message
    ]


def test_accepting_it_silences_the_warning_completely(tmp_path: Path) -> None:
    """Silent, not downgraded. The acceptance is visible in the mapping; an
    info line every build is the same noise one rung down, and a notice nobody
    can resolve is a notice everyone learns to skim."""
    schema, bundle = _calculated_display_inputs(tmp_path, accepted=True)
    assert not [
        f for f in validate_against_mapping(schema, bundle)
        if "display_column" in f.message
    ]


def _display_type_inputs(
    tmp_path: Path, column_type: str, *, looked_up: bool,
) -> tuple[Schema, MappingBundle]:
    follow_up = (
        "Table FollowUp {\n"
        "  Id int [pk, increment]\n"
        "  Event int [ref: > Event.Id]\n"
        "}\n"
        if looked_up else ""
    )
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Event {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar\n"
        f"  Notes {column_type}\n"
        "}\n" + follow_up,
        encoding="utf-8",
    )
    entities = (
        "  Event: { kind: List, base_template: 100, site_role: default, "
        "display_column: Notes }\n"
    )
    if looked_up:
        entities += "  FollowUp: { kind: List, base_template: 100, site_role: default }\n"
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\nentities:\n' + entities, encoding="utf-8",
    )
    return parse_dbml(tmp_path / "s.dbml"), load_mapping(tmp_path / "m.yaml")


@pytest.mark.parametrize(
    ("column_type", "described_as"),
    [
        ("longtext", "Multiple lines of text (Note)"),
        ("richtext", "Multiple lines of text (Note)"),
        ("hyperlink", "Hyperlink"),
    ],
)
def test_an_unindexable_display_column_type_is_an_error(
    tmp_path: Path, column_type: str, described_as: str,
) -> None:
    """The display column's index is appended by jsgen AFTER validation, so it
    never met the type guard every declared `indexes { }` entry passes. It is a
    deploy abort: _field_reconcile.js.j2 MERGEs Indexed=true, reads it back and
    throws part-way through a run. An ERROR, not a warning — no acceptance can
    make a Note column indexable."""
    schema, bundle = _display_type_inputs(tmp_path, column_type, looked_up=True)
    errors = [
        f.message
        for f in validate_against_mapping(schema, bundle)
        if f.severity == "error" and "display_column" in f.message
    ]
    assert len(errors) == 1, errors
    assert "Notes" in errors[0]
    assert described_as in errors[0]
    assert "cannot index" in errors[0]


def test_an_unindexable_display_column_is_fine_when_nothing_looks_it_up(
    tmp_path: Path,
) -> None:
    """No lookup into it means no implicit index, so there is nothing to refuse.
    Erroring here would ban a perfectly good Note column from being the label a
    report happens to print."""
    schema, bundle = _display_type_inputs(tmp_path, "longtext", looked_up=False)
    assert not [
        f for f in validate_against_mapping(schema, bundle)
        if f.severity == "error" and "display_column" in f.message
    ]


def test_a_display_column_that_is_never_rendered_is_an_error(tmp_path: Path) -> None:
    """A cross-site logical column is declared in the DBML but replaced at deploy
    time by generated Abbreviation and SiteUrl fields, so it never exists on the
    list. _naming.py cannot see this — the name IS a declared column — and the
    implicit index would be created on a field that is not there."""
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Region {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar\n"
        "}\n"
        "Table Event {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar\n"
        "  Region int [ref: > Region.Id]\n"
        "}\n"
        "Table FollowUp {\n"
        "  Id int [pk, increment]\n"
        "  Event int [ref: > Event.Id]\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Region: { kind: List, base_template: 100, site_role: default }\n"
        "  Event: { kind: List, base_template: 100, site_role: default, "
        "display_column: Region }\n"
        "  FollowUp: { kind: List, base_template: 100, site_role: default }\n"
        "cross_site_reference_columns:\n"
        "  - { entity: Event, column: Region }\n",
        encoding="utf-8",
    )
    errors = [
        f.message
        for f in validate_against_mapping(
            parse_dbml(tmp_path / "s.dbml"), load_mapping(tmp_path / "m.yaml"),
        )
        if f.severity == "error" and "display_column" in f.message
    ]
    assert len(errors) == 1, errors
    assert "not a rendered column" in errors[0]
    assert "Abbreviation" in errors[0]


def test_a_pointless_acceptance_warns(tmp_path: Path) -> None:
    """Set where the display column is perfectly indexable, it signals a
    misunderstanding rather than a decision."""
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Event {\n"
        "  Id int [pk, increment]\n"
        "  Ref nvarchar\n"
        "}\n"
        "Table FollowUp {\n"
        "  Id int [pk, increment]\n"
        "  Event int [ref: > Event.Id]\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Event: { kind: List, base_template: 100, site_role: default, "
        "display_column: Ref, accept_unindexable_display_column: true }\n"
        "  FollowUp: { kind: List, base_template: 100, site_role: default }\n",
        encoding="utf-8",
    )
    warnings = [
        f.message
        for f in validate_against_mapping(
            parse_dbml(tmp_path / "s.dbml"), load_mapping(tmp_path / "m.yaml"),
        )
        if f.severity == "warning"
        and "accept_unindexable_display_column" in f.message
    ]
    assert len(warnings) == 1
    assert "is not calculated" in warnings[0]


def test_an_acceptance_on_an_unlooked_up_calculated_column_states_the_truth(
    tmp_path: Path,
) -> None:
    """Not a lookup target, display column IS calculated, key set. The verdict
    (remove it) is right, but the message used to say "the display column
    'Label' is not calculated" about a column that is. The combination had no
    test, which is why the false message shipped."""
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Event {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar\n"
        "  Label calculated_text\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Event: { kind: List, base_template: 100, site_role: default, "
        "display_column: Label, accept_unindexable_display_column: true }\n"
        "calculated_formulas:\n"
        "  Event:\n"
        '    Label: "=[Title]"\n',
        encoding="utf-8",
    )
    warnings = [
        f.message
        for f in validate_against_mapping(
            parse_dbml(tmp_path / "s.dbml"), load_mapping(tmp_path / "m.yaml"),
        )
        if f.severity == "warning"
        and "accept_unindexable_display_column" in f.message
    ]
    assert len(warnings) == 1
    assert "nothing looks this entity up" in warnings[0]
    # 'Label' IS calculated. Saying otherwise is simply untrue.
    assert "is not calculated" not in warnings[0]
    assert "Remove it" in warnings[0]


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


def test_view_previous_titles_cannot_collide_or_claim_all_items(tmp_path: Path) -> None:
    errors = _view_errors(
        tmp_path,
        "views:\n"
        "  Project:\n"
        "    - title: Open\n"
        "      renamed_from: [Open, All Items, Legacy]\n"
        "      fields: [Title]\n"
        "    - title: Closed\n"
        "      renamed_from: [Legacy, Open]\n"
        "      fields: [Title]\n",
    )
    assert any("Open" in f.message and "own title" in f.message for f in errors)
    assert any("All Items" in f.message and "reserved" in f.message for f in errors)
    assert any("Legacy" in f.message and "more than one" in f.message for f in errors)
    assert any("Open" in f.message and "current title" in f.message for f in errors)


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


def test_unindexed_view_filter_warns_with_threshold_and_fields(tmp_path: Path) -> None:
    schema, bundle = _view_inputs(
        tmp_path,
        "views:\n"
        "  Project:\n"
        "    - title: Due work\n"
        "      fields: [Title, Status, DueDate]\n"
        "      where:\n"
        "        any_of:\n"
        "          - { field: Status, op: is_not_null }\n"
        "          - { field: DueDate, op: geq, value: today }\n",
    )
    warnings = [
        finding.message
        for finding in validate_against_mapping(schema, bundle)
        if finding.severity == "warning" and "effective index" in finding.message
    ]
    assert len(warnings) == 1
    assert "Due work" in warnings[0]
    assert "DueDate" in warnings[0] and "Status" in warnings[0]
    assert "5,000" in warnings[0]
    # One indexed condition suffices and its position is irrelevant — measured
    # at 6,000 items, both orderings of a degenerate AND served. Selectivity is
    # the caveat that survives, so the message must still carry one.
    assert "position in the filter does not matter" in warnings[0]
    assert "selectivity does" in warnings[0]
    assert "filter order" not in warnings[0]


def test_explicit_or_unique_filter_index_clears_warning(tmp_path: Path) -> None:
    schema, bundle = _view_inputs(
        tmp_path,
        "views:\n"
        "  Project:\n"
        "    - title: Open work\n"
        "      fields: [Title, Status]\n"
        "      where: [{ field: Status, op: eq, value: Open }]\n"
        "    - title: Ordered work\n"
        "      fields: [Title, SortOrder]\n"
        "      where: [{ field: SortOrder, op: gt, value: 0 }]\n",
    )
    table = schema.tables[0]
    table.indexes.append(TableIndex(("Status",)))
    next(column for column in table.columns if column.name == "SortOrder").unique = True
    warnings = [
        finding.message
        for finding in validate_against_mapping(schema, bundle)
        if finding.severity == "warning" and "view threshold" in finding.message
    ]
    assert not warnings


def test_native_id_filter_and_view_without_filter_do_not_warn(tmp_path: Path) -> None:
    schema, bundle = _view_inputs(
        tmp_path,
        "views:\n"
        "  Project:\n"
        "    - title: By id\n"
        "      fields: [Title, ID]\n"
        "      where: [{ field: ID, op: gt, value: 100 }]\n"
        "    - title: Everything\n"
        "      fields: [Title]\n",
    )
    warnings = [
        finding.message
        for finding in validate_against_mapping(schema, bundle)
        if finding.severity == "warning" and "view threshold" in finding.message
    ]
    assert not warnings


def test_indexed_lookup_filter_does_not_warn(tmp_path: Path) -> None:
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Parent {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar [not null]\n"
        "}\n"
        "Table Child {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar [not null]\n"
        "  Parent int [ref: > Parent.Id]\n"
        "  indexes { Parent }\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Parent: { kind: List, base_template: 100, site_role: default }\n"
        "  Child: { kind: List, base_template: 100, site_role: default }\n"
        "views:\n"
        "  Child:\n"
        "    - title: By parent\n"
        "      fields: [Title, Parent]\n"
        "      where: [{ field: Parent, op: eq, value: 1 }]\n",
        encoding="utf-8",
    )
    findings = validate_against_mapping(
        parse_dbml(tmp_path / "s.dbml"),
        load_mapping(tmp_path / "m.yaml"),
    )
    # No threshold warning at all: the only filter column IS indexed, and an
    # index on a Lookup counts. Asserted over every threshold finding rather
    # than the old "indexed filter" phrasing, so a warning reintroduced under
    # any wording fails here.
    warnings = [
        finding.message
        for finding in findings
        if finding.severity == "warning"
        and "list view threshold" in finding.message
    ]
    assert warnings == []


@pytest.mark.parametrize(
    "display_column",
    [None, "Label"],
    ids=["default_title", "declared_display_column"],
)
def test_view_filtered_on_lookup_targets_display_column_does_not_warn(
    tmp_path: Path, display_column: str | None,
) -> None:
    """Locks in what Task 2 exists to produce: a lookup target's display
    column carries an implicit index (a picker past the 5,000-item threshold
    needs it — see analysis/lookups.py), so THIS check — which only ever
    reads `vc.effective_indexes` — must score a view on the TARGET entity
    that filters on that column as safe, even with no explicit `indexes {}`
    entry naming it. Parameterised over the default display column (Title,
    when the mapping declares nothing) and an explicit `display_column`,
    because Task 2 folds both in the same way.

    Filtering on a different, non-display, unindexed column on the same
    entity must still warn — proving the check still fires at all, so a bug
    that silenced it completely could not pass the first half vacuously.
    """
    filtered_column = display_column or "Title"
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Event {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar [not null]\n"
        "  Label nvarchar\n"
        "  Status nvarchar\n"
        "}\n"
        "Table FollowUp {\n"
        "  Id int [pk, increment]\n"
        "  Event int [ref: > Event.Id]\n"
        "}\n",
        encoding="utf-8",
    )
    display_clause = f", display_column: {display_column}" if display_column else ""
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        f"  Event: {{ kind: List, base_template: 100, site_role: default"
        f"{display_clause} }}\n"
        "  FollowUp: { kind: List, base_template: 100, site_role: default }\n"
        "views:\n"
        "  Event:\n"
        "    - title: Filtered by display\n"
        "      fields: [Title, Label, Status]\n"
        f"      where: [{{ field: {filtered_column}, op: eq, value: X }}]\n"
        "    - title: Filtered by other\n"
        "      fields: [Title, Label, Status]\n"
        "      where: [{ field: Status, op: eq, value: Y }]\n",
        encoding="utf-8",
    )
    findings = validate_against_mapping(
        parse_dbml(tmp_path / "s.dbml"), load_mapping(tmp_path / "m.yaml"),
    )
    threshold_warnings = [
        f.message for f in findings
        if f.severity == "warning" and "list view threshold" in f.message
    ]
    display_warnings = [
        m for m in threshold_warnings if "views[Event].Filtered by display" in m
    ]
    other_warnings = [
        m for m in threshold_warnings if "views[Event].Filtered by other" in m
    ]
    assert display_warnings == [], display_warnings
    assert other_warnings != [], "the check must still warn on a real gap"


def test_indexed_person_filter_does_not_warn(tmp_path: Path) -> None:
    """An indexed Person column counts as a useful index.

    Microsoft classifies Person or Group (single value) as a lookup field and
    documents that indexing one does not avert the threshold. Measured at 6,000
    items with the person projected into the view and the join verified, the
    query was served — see _LOOKUP_FIELD_TYPES for the full evidence and the
    one-line revert.
    """
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Request {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar [not null]\n"
        "  RequestedBy person\n"
        "  indexes { RequestedBy }\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Request: { kind: List, base_template: 100, site_role: default }\n"
        "views:\n"
        "  Request:\n"
        "    - title: My requests\n"
        "      fields: [Title, RequestedBy]\n"
        "      where: [{ field: RequestedBy, op: eq, value: me }]\n",
        encoding="utf-8",
    )
    warnings = [
        finding.message
        for finding in validate_against_mapping(
            parse_dbml(tmp_path / "s.dbml"), load_mapping(tmp_path / "m.yaml"),
        )
        if finding.severity == "warning"
        and "list view threshold" in finding.message
    ]
    # An indexed Person column is a useful index. Measured at 6,000 items with
    # the person projected into the view and the join verified — see
    # _LOOKUP_FIELD_TYPES. This is the personal-work-queue idiom the template
    # library ships, and it needs no remedy.
    assert warnings == []


def test_system_column_filter_is_not_warned_about(tmp_path: Path) -> None:
    """A warning must name a remedy the author can carry out. `Created` is
    filterable but not declarable, so there is no index to add — pydbml
    refuses the declaration outright, which the second half asserts so the
    reason for the silence cannot quietly stop being true."""
    schema, bundle = _view_inputs(
        tmp_path,
        "views:\n"
        "  Project:\n"
        "    - title: Recently raised\n"
        "      fields: [Title, Created]\n"
        "      where: [{ field: Created, op: geq, value: today }]\n",
    )
    warnings = [
        finding.message
        for finding in validate_against_mapping(schema, bundle)
        if finding.severity == "warning" and "list view threshold" in finding.message
    ]
    assert not warnings, warnings

    (tmp_path / "sys.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Project {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar [not null]\n"
        "  indexes { Created }\n"
        "}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Created"):
        parse_dbml(tmp_path / "sys.dbml")


def test_null_only_filter_recommends_an_index(tmp_path: Path) -> None:
    """The library's "blank means still open" idiom. Measured on a matched pair
    at 6,000 items by test/manual/threshold-index-probe.js: the indexed column
    returned all 60 expected rows, the unindexed one returned 50 of 60 with
    HTTP 200 and no error. So the warning names the index as the remedy.

    The message must carry the SILENCE, not just the risk. An author who reads
    "may be truncated" will ship it and wait for the error; there is no error,
    and the view is wrong from the day it is deployed."""
    schema, bundle = _view_inputs(
        tmp_path,
        "views:\n"
        "  Project:\n"
        "    - title: Still open\n"
        "      fields: [Title, DueDate]\n"
        "      where: [{ field: DueDate, op: is_null }]\n",
    )
    warnings = [
        finding.message
        for finding in validate_against_mapping(schema, bundle)
        if finding.severity == "warning" and "list view threshold" in finding.message
    ]
    assert len(warnings) == 1
    assert "Still open" in warnings[0]
    assert "add a bare dbml index" in warnings[0].lower()
    # The null-test remedy, not the comparison one — they differ, and a
    # null-only filter reaching the comparison branch would recommend indexing
    # "a selective filter column" when the only filter column IS the null test.
    assert "50 of 6,000" not in warnings[0]  # the pair is 50 of 60, not of 6,000
    assert "50 of 60" in warnings[0]
    assert "unverified" not in warnings[0]
    # The failure is silent, and the message has to say so. "May be truncated"
    # reads as a risk an author can wait to see; there is nothing to see.
    assert "no error" in warnings[0]


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


@pytest.mark.parametrize("title", ["AllItems", "All-Items", "all items"])
def test_authored_views_cannot_take_the_generated_all_items_url(
    tmp_path: Path, title: str,
) -> None:
    errors = _view_errors(
        tmp_path,
        "views:\n"
        "  Project:\n"
        f"    - title: {title}\n"
        "      fields: [Title]\n",
    )
    assert any("AllItems.aspx" in f.message for f in errors)


def test_cross_site_expansion_cannot_collide_with_declared_columns(tmp_path: Path) -> None:
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Unit {\n"
        "  Id int [pk, increment]\n"
        "}\n"
        "Table Project {\n"
        "  Id int [pk, increment]\n"
        "  Unit int [ref: > Unit.Id]\n"
        "  UnitAbbreviation nvarchar\n"
        "  UnitSiteUrl hyperlink\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Unit: { kind: List, base_template: 100, site_role: default }\n"
        "  Project: { kind: List, base_template: 100, site_role: default }\n"
        "cross_site_reference_columns:\n"
        "  - { entity: Project, column: Unit }\n",
        encoding="utf-8",
    )
    findings = validate_against_mapping(
        parse_dbml(tmp_path / "s.dbml"), load_mapping(tmp_path / "m.yaml"),
    )
    collisions = [f.message for f in findings if "collides" in f.message]
    assert any("UnitAbbreviation" in message for message in collisions)
    assert any("UnitSiteUrl" in message for message in collisions)


def test_demo_refs_and_calendar_dates_are_validated_before_generation(tmp_path: Path) -> None:
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Parent {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar\n"
        "}\n"
        "Table Task {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar\n"
        "  Parent int [ref: > Parent.Id]\n"
        "  Previous int [ref: > Task.Id]\n"
        "  Note nvarchar\n"
        "  DueDate date\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Parent: { kind: List, base_template: 100, site_role: default }\n"
        "  Task: { kind: List, base_template: 100, site_role: default }\n"
        "demo_items:\n"
        "  Parent:\n"
        "    - { key: p1, values: { Title: '[DEMO] Parent' } }\n"
        "  Task:\n"
        "    - key: t1\n"
        "      values:\n"
        "        Title: '[DEMO] First'\n"
        "        Previous: { demo_ref: t2 }\n"
        "        Note: { demo_ref: t1 }\n"
        "        DueDate: '2026-02-31'\n"
        "    - key: t2\n"
        "      values:\n"
        "        Title: '[DEMO] Second'\n"
        "        Parent: { demo_ref: t1 }\n",
        encoding="utf-8",
    )
    findings = validate_against_mapping(
        parse_dbml(tmp_path / "s.dbml"), load_mapping(tmp_path / "m.yaml"),
    )
    errors = [f.message for f in findings if f.severity == "error"]
    assert any("Previous" in message and "before" in message for message in errors)
    assert any("Note" in message and "lookup" in message for message in errors)
    assert any(
        "Parent" in message and "Task" in message and "targets" in message
        for message in errors
    )
    assert any("2026-02-31" in message and "calendar" in message for message in errors)


def test_rendered_validation_formula_length_is_checked(tmp_path: Path) -> None:
    values = ", ".join(f"'value-{i}-{'x' * 40}'" for i in range(24))
    errors = _view_errors(
        tmp_path,
        "list_validation:\n"
        "  Project:\n"
        f"    when: [{{ field: Status, op: in, value: [{values}] }}]\n"
        "    message: Too long.\n"
        "column_validation:\n"
        "  Project:\n"
        "    columns:\n"
        "      Status:\n"
        f"        when: [{{ field: Status, op: in, value: [{values}] }}]\n"
        "        message: Too long.\n",
    )
    overlong = [f.message for f in errors if "1024" in f.message]
    assert any("list_validation" in message for message in overlong)
    assert any("column_validation" in message for message in overlong)


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


def test_all_items_title_is_reserved_for_the_generated_unfiltered_view(
    tmp_path: Path,
) -> None:
    errors = _view_errors(
        tmp_path,
        "views:\n"
        "  Project:\n"
        "    - title: All Items\n"
        "      fields: [Title]\n"
        "      where:\n"
        "        - { field: Status, op: eq, value: Open }\n",
    )
    assert any(
        "All Items" in f.message and "generated" in f.message
        for f in errors
    ), errors


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
    and column_formatting deployed nothing; DBML indexes and
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


def test_calculated_formula_referencing_id_is_rejected() -> None:
    """The reference check compared against the raw DBML column set rather
    than the RENDERED one. `Id int [pk, increment]` is skipped at render
    time — typemap returns Skip and jsgen continues — so a formula naming
    [Id] passed validation and was posted against a column the deploy never
    creates. SharePoint answers HTTP 500 mid-paste, which is exactly what
    this check's own comment says it exists to prevent."""
    table = Table(name="Risk", columns=[
        Column(name="Id", type="int", is_pk=True, is_auto_increment=True),
        Column(name="Title", type="nvarchar", required=True),
        Column(name="Ref", type="calculated_text"),
    ])
    bundle = _bundle_with_formulas({"Risk": {"Ref": '=CONCATENATE("R-",[Id])'}}, "Risk")
    findings = validate_against_mapping(_schema(table), bundle)
    assert any(
        f.severity == "error" and "[Id]" in f.message for f in findings
    ), findings


def test_calculated_formula_referencing_a_phase_two_lookup_is_rejected() -> None:
    """jsgen orders calculated fields only within fields_phase1 and ignores
    phase2_lookups, so a formula naming a DEFERRED lookup was emitted in
    Phase 1 — before the column it references exists. A self-referencing
    lookup is always deferred, so this is reachable from any hierarchy."""
    table = Table(name="Risk", columns=[
        Column(name="Id", type="int", is_pk=True, is_auto_increment=True),
        Column(name="Title", type="nvarchar", required=True),
        Column(name="Parent", type="int", ref=Reference(target_table="Risk", target_column="Id")),
        Column(name="Label", type="calculated_text"),
    ])
    bundle = _bundle_with_formulas({"Risk": {"Label": '=CONCATENATE([Title],[Parent])'}}, "Risk")
    findings = validate_against_mapping(_schema(table), bundle)
    assert any(
        f.severity == "error" and "Parent" in f.message and "Label" in f.message
        for f in findings
    ), findings


def test_calculated_formula_referencing_a_phase_one_column_is_fine() -> None:
    table = Table(name="Risk", columns=[
        Column(name="Id", type="int", is_pk=True, is_auto_increment=True),
        Column(name="Title", type="nvarchar", required=True),
        Column(name="Label", type="calculated_text"),
    ])
    bundle = _bundle_with_formulas({"Risk": {"Label": "=CONCATENATE([Title])"}}, "Risk")
    assert [
        f for f in validate_against_mapping(_schema(table), bundle) if f.severity == "error"
    ] == []


# --- Retired columns --------------------------------------------------------


def test_calculated_formula_pairing_guards_the_retirement_carve_out(
    tmp_path: Path,
) -> None:
    """GUARD. `_apply_retirement` (model/mapping_loader.py) skips the
    form_visibility fold for calculated columns, and identifies them by
    their `calculated_formulas` keys — the loader has never seen the DBML
    and cannot read column types. That is correct ONLY while those keys are
    exactly the set of `calculated_*` columns.

    Both directions of that pairing are asserted below. If you are here
    because you relaxed one of them, go and read `_apply_retirement`'s
    carve-out first: loosening either rule silently lets a calculated
    column reach form_visibility, where the validator rejects it, making
    retiring that column an unfixable build error.
    """
    # Direction 1: a calculated column with NO formula must error.
    (tmp_path / "no-formula.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Board {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar\n"
        "  BoardDate date\n"
        "  Route calculated_text\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "no-formula.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Board: { kind: List, base_template: 100, site_role: default }\n",
        encoding="utf-8",
    )
    findings = validate_against_mapping(
        parse_dbml(tmp_path / "no-formula.dbml"),
        load_mapping(tmp_path / "no-formula.yaml"),
    )
    assert any(
        "Board.Route" in f.message and "has no" in f.message and "formula" in f.message
        for f in findings if f.severity == "error"
    )

    # Direction 2: a formula targeting a NON-calculated column must error.
    (tmp_path / "wrong-target.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Board {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar\n"
        "  BoardDate date\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "wrong-target.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Board: { kind: List, base_template: 100, site_role: default }\n"
        "calculated_formulas:\n"
        "  Board:\n"
        "    BoardDate: '=1'\n",
        encoding="utf-8",
    )
    findings = validate_against_mapping(
        parse_dbml(tmp_path / "wrong-target.dbml"),
        load_mapping(tmp_path / "wrong-target.yaml"),
    )
    assert any(
        "calculated_formulas[Board]" in f.message and "'BoardDate'" in f.message
        for f in findings if f.severity == "error"
    )


def test_retired_columns_errors(tmp_path: Path) -> None:
    """Fail closed where a retirement mistake would break the list. The
    not-null-with-no-default case is the load-bearing one: retirement hides
    the column from the New form, so every subsequent save would fail."""
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Enum rag {\n"
        '  "Green"\n'
        '  "Amber"\n'
        "}\n"
        "Table Board {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar\n"
        "  BoardDate date [not null]\n"
        "  OperationsStatus rag\n"
        "  SiteServicesStatus rag\n"
        "  MustFill nvarchar [not null]\n"
        "  Route calculated_text\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Board: { kind: List, base_template: 100, site_role: default }\n"
        "calculated_formulas:\n"
        "  Board:\n"
        "    Route: '=[OperationsStatus]'\n"
        "list_validation:\n"
        "  Board:\n"
        "    when:\n"
        "      - { field: OperationsStatus, op: is_not_null }\n"
        '    message: "Give a status."\n'
        "column_validation:\n"
        "  Board:\n"
        "    reconcile: declared\n"
        "    columns:\n"
        "      OperationsStatus:\n"
        "        when: [{ field: OperationsStatus, op: is_not_null }]\n"
        '        message: "Needed."\n'
        "retired_columns:\n"
        "  Widget: [Anything]\n"
        "  Board:\n"
        "    Ghost:\n"
        "      retired: 2026-09-01\n"
        "    OperationsStatus:\n"
        "      retired: not-a-date\n"
        "      superseded_by: OperationsStatus\n"
        "    MustFill:\n"
        "      retired: 2026-09-01\n"
        "      superseded_by: Nowhere\n"
        "    SiteServicesStatus:\n"
        "      retired: 2026-09-01\n",
        encoding="utf-8",
    )
    schema = parse_dbml(tmp_path / "s.dbml")
    bundle = load_mapping(tmp_path / "m.yaml")
    errors = [
        f for f in validate_against_mapping(schema, bundle) if f.severity == "error"
    ]

    def has(*needles: str) -> bool:
        return any(all(n in f.message for n in needles) for f in errors)

    # Unknown entity, and a column the DBML does not declare.
    assert has("retired_columns[Widget]", "unknown entity")
    assert has("retired_columns[Board]", "'Ghost'", "not a rendered column")
    # Unparseable retirement date.
    assert has("retired_columns[Board].OperationsStatus", "not an ISO date")
    # superseded_by pointing at itself, and at nothing.
    assert has("retired_columns[Board].OperationsStatus", "the retired column itself")
    assert has("retired_columns[Board].MustFill", "'Nowhere'", "not a rendered column")
    # not null with no declared default — the escalation, reported against
    # retirement rather than against a form_visibility section nobody wrote.
    assert has("retired_columns[Board]", "'MustFill'", "every save would fail")
    # Live formulas referencing a retired column.
    assert has("calculated_formulas[Board].Route", "[OperationsStatus]", "retired")
    assert has("list_validation[Board]", "OperationsStatus", "retired")
    # A save rule ON a retired column: retirement hides it from the new form,
    # so is_not_null there rejects every new item with no field to satisfy
    # it. The list silently stops accepting rows.
    assert has("column_validation[Board].OperationsStatus", "retired", "every new item")


def test_retired_supersession_may_not_name_another_retirement(tmp_path: Path) -> None:
    """Superseding one dead column with another leaves the operator with no
    live destination for the data."""
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Board {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar\n"
        "  OldA nvarchar\n"
        "  OldB nvarchar\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Board: { kind: List, base_template: 100, site_role: default }\n"
        "retired_columns:\n"
        "  Board:\n"
        "    OldA:\n"
        "      retired: 2026-09-01\n"
        "      superseded_by: OldB\n"
        "    OldB:\n"
        "      retired: 2026-09-01\n",
        encoding="utf-8",
    )
    schema = parse_dbml(tmp_path / "s.dbml")
    bundle = load_mapping(tmp_path / "m.yaml")
    errors = [
        f for f in validate_against_mapping(schema, bundle) if f.severity == "error"
    ]
    assert any(
        "retired_columns[Board].OldA" in f.message and "itself retired" in f.message
        for f in errors
    )


def test_retiring_an_undeployable_column_is_rejected(tmp_path: Path) -> None:
    """Retirement resolves into a per-column declaration, and the built-in
    Title never receives one — it is provisioned through its own patch. A
    retirement that cannot be carried out must say so rather than validate
    clean and deploy nothing."""
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Board {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar\n"
        "  BoardDate date\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Board: { kind: List, base_template: 100, site_role: default }\n"
        "retired_columns:\n"
        "  Board: [Title]\n",
        encoding="utf-8",
    )
    schema = parse_dbml(tmp_path / "s.dbml")
    bundle = load_mapping(tmp_path / "m.yaml")
    errors = [
        f for f in validate_against_mapping(schema, bundle) if f.severity == "error"
    ]
    assert any(
        "retired_columns[Board]" in f.message and "'Title'" in f.message
        for f in errors
    )
    # The message is the one the undeployable-column rule already owns, so
    # the two cannot drift; only the context says where to fix it.
    assert any("its own patch" in f.message for f in errors)


def test_retired_calculated_column_is_not_an_unfixable_build_error(
    tmp_path: Path,
) -> None:
    """Retiring a calculated column must be possible. It is never folded
    into form_visibility, so the validator's "calculated columns never
    appear on entry forms" error must not fire."""
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Board {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar\n"
        "  BoardDate date\n"
        "  Route calculated_text\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Board: { kind: List, base_template: 100, site_role: default }\n"
        "calculated_formulas:\n"
        "  Board:\n"
        "    Route: '=[BoardDate]'\n"
        "retired_columns:\n"
        "  Board:\n"
        "    Route:\n"
        "      retired: 2026-09-01\n",
        encoding="utf-8",
    )
    schema = parse_dbml(tmp_path / "s.dbml")
    bundle = load_mapping(tmp_path / "m.yaml")
    findings = validate_against_mapping(schema, bundle)
    assert not [f for f in findings if f.severity == "error"]
    assert "Board" not in bundle.mapping.form_visibility


def test_retired_calculated_column_without_a_formula_reports_only_root_cause(
    tmp_path: Path,
) -> None:
    """The one wrong answer the loader's calculated-column heuristic can
    give. The author declared a calculated column and forgot its formula,
    so `_apply_retirement` cannot tell it is calculated and folds it into
    form_visibility. The build must report the missing formula and NOTHING
    else — blaming the author for a form_visibility entry they never wrote
    buries the error they can actually act on."""
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Board {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar\n"
        "  BoardDate date\n"
        "  Route calculated_text\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Board: { kind: List, base_template: 100, site_role: default }\n"
        "retired_columns:\n"
        "  Board: [Route]\n",
        encoding="utf-8",
    )
    schema = parse_dbml(tmp_path / "s.dbml")
    bundle = load_mapping(tmp_path / "m.yaml")
    # The loader could not know Route was calculated, so it DID fold it.
    assert "Route" in bundle.mapping.form_visibility["Board"].columns

    errors = [
        f for f in validate_against_mapping(schema, bundle) if f.severity == "error"
    ]
    assert len(errors) == 1, [f.message for f in errors]
    assert "Board.Route" in errors[0].message
    assert "calculated_formulas.Board.Route" in errors[0].message


def test_retired_columns_warnings(tmp_path: Path) -> None:
    """Warn where a retirement mistake only wastes something. Retirement
    must never break a build: a stale view or width reference is stripped
    and reported, not rejected. A column_formatting entry on a retired
    column is KEPT deliberately — historical values still render with their
    severity colours wherever the column is still shown."""
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
        "  Stamp nvarchar [not null, default: 'x']\n"
        "  indexes { OperationsStatus }\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Board: { kind: List, base_template: 100, site_role: default }\n"
        "display_names:\n"
        "  mode: auto\n"
        "column_formatting:\n"
        "  Board:\n"
        "    OperationsStatus: { style: severity, map: { Green: good } }\n"
        "form_formatting:\n"
        "  Board:\n"
        "    body:\n"
        "      sections:\n"
        '        - displayname: "Header"\n'
        "          fields: [BoardDate, OperationsStatus]\n"
        "views:\n"
        "  Board:\n"
        '    - title: "Heat grid"\n'
        "      fields: [BoardDate, OperationsStatus]\n"
        "      widths: { OperationsStatus: 120 }\n"
        '    - title: "Statuses only"\n'
        "      fields: [OperationsStatus]\n"
        "retired_columns:\n"
        "  Board:\n"
        "    OperationsStatus:\n"
        "      retired: 2026-09-01\n"
        "    Stamp:\n"
        "      retired: 2026-09-01\n",
        encoding="utf-8",
    )
    schema = parse_dbml(tmp_path / "s.dbml")
    bundle = load_mapping(tmp_path / "m.yaml")
    findings = validate_against_mapping(schema, bundle)
    warnings = [f for f in findings if f.severity == "warning"]

    def warned(*needles: str) -> bool:
        return any(all(n in f.message for n in needles) for f in warnings)

    # not null WITH a default: saves succeed, the default is stamped forever.
    assert warned("retired_columns[Board]", "'Stamp'", "stamped with")
    # A dead index is dead weight against a finite per-list budget.
    assert warned("retired_columns[Board]", "'OperationsStatus'", "indexes block")
    # Stripped view field, width and form-section references — reported,
    # never rejected. One generic loop over retirement_strips covers all
    # three; the context string is what distinguishes them.
    assert warned("views[Board].Heat grid fields", "stripped it")
    assert warned("views[Board].Heat grid widths", "stripped it")
    assert warned("form_formatting[Board].body sections", "stripped it")
    # A view left with no fields at all.
    assert warned("views[Board].Statuses only", "every declared field")
    # Never an error: retirement must not break a build.
    assert not [f for f in findings if f.severity == "error"]
    # column_formatting on a retired column is kept, not flagged.
    assert not warned("column_formatting")


def test_retirement_without_display_names_warns_the_suffix_is_inert(
    tmp_path: Path,
) -> None:
    """display_name_for ignores overrides unless mode is auto, so without a
    display_names section the ' (retired)' suffix never reaches SharePoint."""
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Board {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar\n"
        "  OldColumn nvarchar\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Board: { kind: List, base_template: 100, site_role: default }\n"
        "retired_columns:\n"
        "  Board: [OldColumn]\n",
        encoding="utf-8",
    )
    schema = parse_dbml(tmp_path / "s.dbml")
    bundle = load_mapping(tmp_path / "m.yaml")
    warnings = [
        f for f in validate_against_mapping(schema, bundle) if f.severity == "warning"
    ]
    assert any(
        "display_names is not enabled" in f.message and "(retired)" in f.message
        for f in warnings
    )


def test_retirement_replacing_a_form_visibility_declaration_warns(
    tmp_path: Path,
) -> None:
    """The fold overwrites a hand-written declaration for a retired column.
    Silent mutation of the author's own YAML is exactly what the strip
    record exists to surface."""
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Board {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar\n"
        "  OldColumn nvarchar\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Board: { kind: List, base_template: 100, site_role: default }\n"
        "form_visibility:\n"
        "  Board:\n"
        "    columns:\n"
        "      OldColumn: visible\n"
        "retired_columns:\n"
        "  Board: [OldColumn]\n",
        encoding="utf-8",
    )
    schema = parse_dbml(tmp_path / "s.dbml")
    bundle = load_mapping(tmp_path / "m.yaml")
    findings = validate_against_mapping(schema, bundle)
    assert any(
        f.severity == "warning"
        and "form_visibility[Board].columns" in f.message
        and "stripped it" in f.message
        for f in findings
    )


# --- Field sets -------------------------------------------------------------


def test_field_set_on_unknown_entity_is_error(tmp_path: Path) -> None:
    errors = _view_errors(
        tmp_path,
        "field_sets:\n  Widget:\n    header: [Title]\n",
    )
    assert any(
        "field_sets" in f.message
        and "Widget" in f.message
        and "unknown entity" in f.message
        for f in errors
    )


def test_field_set_member_must_be_a_rendered_column(tmp_path: Path) -> None:
    """The declaration message is the one that says where to fix it."""
    errors = _view_errors(
        tmp_path,
        "field_sets:\n  Project:\n    header: [Title, Nope]\n"
        "views:\n"
        "  Project:\n"
        "    - title: V\n"
        '      fields: ["@header"]\n',
    )
    assert any(
        "field_sets[Project].header" in f.message and "Nope" in f.message
        for f in errors
    )
    assert not any("'Title'" in f.message for f in errors)


def test_view_referencing_an_undeclared_field_set_is_error(tmp_path: Path) -> None:
    errors = _view_errors(
        tmp_path,
        "field_sets:\n  Project:\n    header: [Title]\n"
        "views:\n"
        "  Project:\n"
        "    - title: V\n"
        '      fields: ["@headr"]\n',
    )
    assert any("@headr" in f.message and "field set" in f.message for f in errors)
    # One precise error, not that plus a confusing "not a rendered column".
    assert not any(
        "rendered column" in f.message and "headr" in f.message for f in errors
    )


def test_field_set_name_cannot_contain_the_reference_marker(tmp_path: Path) -> None:
    errors = _view_errors(
        tmp_path,
        'field_sets:\n  Project:\n    "hea@der": [Title]\n',
    )
    assert any(
        "field_sets[Project].hea@der" in f.message and "'@'" in f.message
        for f in errors
    )


def test_empty_field_set_is_error(tmp_path: Path) -> None:
    errors = _view_errors(
        tmp_path,
        "field_sets:\n  Project:\n    header: []\n",
    )
    assert any(
        "field_sets[Project].header" in f.message and "empty" in f.message
        for f in errors
    )


def test_valid_field_set_produces_no_errors(tmp_path: Path) -> None:
    errors = _view_errors(
        tmp_path,
        "field_sets:\n  Project:\n    header: [Title, Status]\n"
        "views:\n"
        "  Project:\n"
        "    - title: V\n"
        '      fields: ["@header", DueDate]\n',
    )
    assert errors == []


def test_unreferenced_field_set_is_a_warning(tmp_path: Path) -> None:
    """Dead config wastes nothing but the reader's time, so it warns rather
    than failing the build — the fail-closed line is drawn at declarations
    that would break the list."""
    schema, bundle = _view_inputs(
        tmp_path,
        "field_sets:\n"
        "  Project:\n"
        "    header: [Title]\n"
        "    orphan: [Status]\n"
        "views:\n"
        "  Project:\n"
        "    - title: V\n"
        '      fields: ["@header"]\n',
    )
    findings = validate_against_mapping(schema, bundle)
    assert any(
        f.severity == "warning"
        and "field_sets[Project].orphan" in f.message
        and "@orphan" in f.message
        for f in findings
    )
    assert not any("field_sets[Project].header" in f.message for f in findings)


def test_retired_column_in_a_field_set_is_a_warning(tmp_path: Path) -> None:
    """Expansion runs first, so the column is stripped from every view that
    pulls the set in and the strip is recorded against the VIEW. The set
    itself is where the author fixes it, so it gets its own warning naming
    the set — otherwise the only report points at a view that no longer
    mentions the column."""
    schema, bundle = _view_inputs(
        tmp_path,
        "field_sets:\n"
        "  Project:\n"
        "    header: [Title, Status]\n"
        "views:\n"
        "  Project:\n"
        "    - title: V\n"
        '      fields: ["@header"]\n'
        "retired_columns:\n"
        "  Project:\n"
        "    Status:\n"
        "      retired: 2026-09-01\n",
    )
    findings = validate_against_mapping(schema, bundle)
    assert bundle.mapping.views["Project"][0].fields == ["Title"]
    assert any(
        f.severity == "warning"
        and "field_sets[Project].header" in f.message
        and "'Status'" in f.message
        and "retired" in f.message
        for f in findings
    )
    assert not [f for f in findings if f.severity == "error"]


def test_view_formatting_may_only_read_columns_the_view_displays(tmp_path: Path) -> None:
    """SharePoint resolves a view formatter's [$Field] against the columns
    that view renders, not the list's columns — "reference to other fields
    will work only if they are included in the same view". A reference to a
    real column the view omits therefore resolves to nothing: the format
    silently never fires, the build exits 0, and the only symptom is a row
    wash nobody sees. Catching it needs the VIEW's field list, which is why
    checking against the table's columns was not enough."""
    errors = _view_errors(
        tmp_path,
        "views:\n"
        "  Project:\n"
        "    - title: V\n"
        "      fields: [Title]\n"
        "      formatting: { additionalRowClass: \"=if([$Status] == 'Open', 'x', '')\" }\n",
    )
    assert any(
        "Status" in f.message and "V" in f.message for f in errors
    ), f"a formatter reading a column the view does not show must be refused: {errors}"

    # The same reference is fine once the view actually shows the column.
    ok = _view_errors(
        tmp_path,
        "views:\n"
        "  Project:\n"
        "    - title: V\n"
        "      fields: [Title, Status]\n"
        "      formatting: { additionalRowClass: \"=if([$Status] == 'Open', 'x', '')\" }\n",
    )
    assert ok == [], ok


def test_view_formatting_may_only_read_system_columns_the_view_displays(
    tmp_path: Path,
) -> None:
    errors = _view_errors(
        tmp_path,
        "views:\n"
        "  Project:\n"
        "    - title: V\n"
        "      fields: [Title]\n"
        "      formatting: { additionalRowClass: \"=if([$Created] != '', 'x', '')\" }\n",
    )
    assert any("Created" in f.message and "does not display" in f.message for f in errors), (
        f"a formatter cannot read an omitted system column: {errors}"
    )

    ok = _view_errors(
        tmp_path,
        "views:\n"
        "  Project:\n"
        "    - title: V\n"
        "      fields: [Title, Created]\n"
        "      formatting: { additionalRowClass: \"=if([$Created] != '', 'x', '')\" }\n",
    )
    assert ok == [], ok


def _calculated_form_inputs(tmp_path: Path, block: str) -> tuple[Schema, MappingBundle]:
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Project {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar [not null]\n"
        "  Score int\n"
        "  Band calculated_text\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Project: { kind: List, base_template: 100, site_role: default }\n"
        "calculated_formulas:\n"
        "  Project:\n"
        "    Band: '=IF([Score]>5,\"High\",\"Low\")'\n"
        + block,
        encoding="utf-8",
    )
    return parse_dbml(tmp_path / "s.dbml"), load_mapping(tmp_path / "m.yaml")


def test_a_form_header_may_not_read_a_calculated_column(tmp_path: Path) -> None:
    """A calculated column resolves to an empty string in a form header or
    footer — verified on a live tenant against a saved item that had a
    value. Nothing errors: the header renders, that one value is blank. The
    deploy cannot see it either, because the formatter saves and reads back
    byte-identical. So the build is the only place it can be caught.

    Body sections are exempt: they list field NAMES rather than reading
    values, and a calculated column placed in one renders on the Display
    form exactly as intended."""
    schema, bundle = _calculated_form_inputs(
        tmp_path,
        "form_formatting:\n"
        "  Project:\n"
        "    header: { elmType: div, txtContent: '=[$Band]' }\n",
    )
    errors = [
        f for f in validate_against_mapping(schema, bundle) if f.severity == "error"
    ]
    assert any(
        "Band" in f.message and "calculated" in f.message.lower() for f in errors
    ), f"a header reading a calculated column must be refused: {errors}"

    # A non-calculated reference is fine, and so is the same calculated
    # column named in a body section.
    schema, bundle = _calculated_form_inputs(
        tmp_path,
        "form_formatting:\n"
        "  Project:\n"
        "    header: { elmType: div, txtContent: '=[$Title]' }\n"
        "    body: { sections: [ { displayname: X, fields: [Title, Band] } ] }\n",
    )
    ok = [f for f in validate_against_mapping(schema, bundle) if f.severity == "error"]
    assert ok == [], ok


def test_the_calculated_type_vocabulary_is_enumerated_in_exactly_one_place() -> None:
    """No collection may re-list the three calculated DBML types.

    They belong to typemap's CALCULATED_OUTPUT_TYPES, because each needs an
    SP OutputType — a calculated type without one cannot deploy, which is
    what forces that map to stay complete and makes its keys authoritative.
    Everywhere else derives from CALCULATED_TYPES.

    A second copy is not a style problem: it is a set that can disagree
    with the first. Add a fourth calculated type and the copy is silently
    short, so every check reading it quietly stops covering the new type
    while the suite stays green.

    The rule is per-COLLECTION, not per-file. `conditions.py` legitimately
    names calculated_number in its numeric types, calculated_date in its
    date types and calculated_text in its measurable types — three
    different classifications that each happen to include one. That is not
    a copy of the vocabulary; a single literal holding all three is.
    """
    names = {"calculated_text", "calculated_number", "calculated_date"}
    src = Path(__file__).parent.parent / "src" / "dbml_sharepoint"
    offenders: list[str] = []
    for path in sorted(src.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Set | ast.List | ast.Tuple):
                literals = {
                    e.value for e in node.elts
                    if isinstance(e, ast.Constant) and isinstance(e.value, str)
                }
            elif isinstance(node, ast.Dict):
                literals = {
                    k.value for k in node.keys
                    if isinstance(k, ast.Constant) and isinstance(k.value, str)
                }
            else:
                continue
            if names <= literals:
                offenders.append(path.relative_to(src).as_posix())
                break
    assert offenders == ["analysis/typemap.py"], (
        f"the calculated type vocabulary is enumerated in {offenders}; it "
        f"belongs only in analysis/typemap.py, with everything else "
        f"deriving from CALCULATED_TYPES"
    )


# --- Three refusals for mistakes a deploy cannot see -------------------------
#
# A fourth was considered and NOT added: refusing a `widths` key that names a
# field the view does not display already exists above.


def test_group_by_need_not_be_one_of_the_views_own_fields(tmp_path: Path) -> None:
    """SharePoint renders the grouped value in the group HEADER, from the
    GroupBy FieldRef itself, so grouping by a column the view does not also
    list is a normal way to avoid repeating one value in every row.

    Only the weaker rule holds: the column must exist on the entity.
    """
    errors = _view_errors(
        tmp_path,
        "views:\n  Project:\n    - title: By status\n      fields: [Title]\n"
        "      group_by: { field: Status }\n",
    )
    assert not [f for f in errors if "group_by" in f.message], errors


def test_group_by_on_an_unknown_column_is_still_refused(tmp_path: Path) -> None:
    errors = _view_errors(
        tmp_path,
        "views:\n  Project:\n    - title: By ghost\n      fields: [Title]\n"
        "      group_by: { field: Ghost }\n",
    )
    assert any("Ghost" in f.message for f in errors), errors


def test_group_by_in_the_views_fields_is_accepted(tmp_path: Path) -> None:
    errors = _view_errors(
        tmp_path,
        "views:\n"
        "  Project:\n"
        "    - title: By status\n"
        "      fields: [Title, Status]\n"
        "      group_by: { field: Status }\n",
    )
    assert not [f for f in errors if "group_by" in f.message], errors


def test_a_body_section_hidden_from_every_form_is_refused(tmp_path: Path) -> None:
    """The section renders as a heading with nothing under it. Asserted of a
    NON-LAST section: Learn documents that unreferenced columns are appended
    to the last one, so only an earlier section can be provably empty."""
    schema, bundle = _calculated_form_inputs(
        tmp_path,
        "form_visibility:\n"
        "  Project:\n"
        "    columns:\n"
        "      Score: { new: false, existing: false }\n"
        "form_formatting:\n"
        "  Project:\n"
        "    body:\n"
        "      sections:\n"
        "        - { displayname: Hidden, fields: [Score] }\n"
        "        - { displayname: Everything else, fields: [Title, Band] }\n",
    )
    errors = [f for f in validate_against_mapping(schema, bundle) if f.severity == "error"]
    assert any(
        "Hidden" in f.message and "bare heading" in f.message for f in errors
    ), errors


def test_the_last_section_may_be_empty_because_it_is_the_catch_all(tmp_path: Path) -> None:
    """Learn: "A column not referenced in any of the sections will be
    automatically referenced in the last section." risk-register's System
    section is exactly this shape and its DEPLOY.md documents the bare
    heading on the New form as cosmetic and expected."""
    schema, bundle = _calculated_form_inputs(
        tmp_path,
        "form_visibility:\n"
        "  Project:\n"
        "    columns:\n"
        "      Score: { new: false, existing: false }\n"
        "form_formatting:\n"
        "  Project:\n"
        "    body:\n"
        "      sections:\n"
        "        - { displayname: Everything else, fields: [Title, Band] }\n"
        "        - { displayname: System, fields: [Score] }\n",
    )
    errors = [f for f in validate_against_mapping(schema, bundle) if f.severity == "error"]
    assert not [f for f in errors if "bare heading" in f.message], errors


def test_a_column_in_no_section_warns_rather_than_failing(tmp_path: Path) -> None:
    """It is drift, not breakage: SharePoint appends the column to the last
    section, so the form renders it. What is lost is the guarantee that the
    declared arrangement is the deployed one — and every column added later
    lands in that same section."""
    schema, bundle = _calculated_form_inputs(
        tmp_path,
        "form_formatting:\n"
        "  Project:\n"
        "    body:\n"
        "      sections:\n"
        "        - { displayname: Main, fields: [Title] }\n",
    )
    findings = validate_against_mapping(schema, bundle)
    assert not [f for f in findings if f.severity == "error"], findings
    warnings = [f for f in findings if f.severity == "warning"]
    assert any("Score" in f.message and "Band" in f.message for f in warnings), warnings


def test_a_retired_column_in_no_section_does_not_warn(tmp_path: Path) -> None:
    """Retirement STRIPS a column from body sections on purpose, and warns
    separately about the declarations it rewrote. Warning again here would
    ask the author to re-add exactly what the fold just removed — which is
    what the first version of the rule did to tiered-huddle."""
    schema, bundle = _calculated_form_inputs(
        tmp_path,
        "retired_columns:\n"
        "  Project:\n"
        "    Score: { retired: '2026-01-01', reason: 'superseded' }\n"
        "form_formatting:\n"
        "  Project:\n"
        "    body:\n"
        "      sections:\n"
        "        - { displayname: Main, fields: [Title, Band] }\n",
    )
    findings = validate_against_mapping(schema, bundle)
    assert not [
        f for f in findings if f.severity == "warning" and "in no section" in f.message
    ], findings


def test_demo_items_on_a_document_library_are_refused(tmp_path: Path) -> None:
    """A library's items ARE files. demo-data.js posts to /items, which asks
    SharePoint to create a library row with nothing behind it.

    This built GREEN until the policy-library uplift went looking: the
    bundle would have shipped and failed at paste time, in front of whoever
    was being shown the demo — which is the audience this tool's fail-closed
    posture exists to protect.
    """
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Docs {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar [not null]\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Docs: { kind: DocumentLibrary, base_template: 101, site_role: default }\n"
        "demo_items:\n"
        "  Docs:\n"
        "    - key: d1\n"
        "      values:\n"
        '        Title: "[DEMO] A document"\n',
        encoding="utf-8",
    )
    schema, bundle = parse_dbml(tmp_path / "s.dbml"), load_mapping(tmp_path / "m.yaml")
    errors = [f for f in validate_against_mapping(schema, bundle) if f.severity == "error"]
    assert any(
        "DocumentLibrary" in f.message and "SPFileCollection.Add()" in f.message
        for f in errors
    ), errors


def test_a_document_library_entity_is_refused_outright(tmp_path: Path) -> None:
    """`kind: DocumentLibrary` fails the build, with or without demo rows.

    A library's items are files and this tool writes list rows. Probed on a
    tenant (test/manual/document-library-probe.js, 2026-07-29): SharePoint
    answers a POST to a library's /items with "To add an item to a document
    library, use SPFileCollection.Add()", and an uploaded file reads back
    with `Title: null`, so the standard form header renders blank.

    Half-support — a library that provisions but carries no usable header,
    no view naming its files and no demo rows — reads as a bug in every
    direction, so the kind is refused until that work is done. The message
    must offer the way round, because an adopter hitting this needs to know
    a List plus a hyperlink column is the supported shape.
    """
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Docs {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar [not null]\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Docs: { kind: DocumentLibrary, base_template: 101, site_role: default }\n",
        encoding="utf-8",
    )
    schema, bundle = parse_dbml(tmp_path / "s.dbml"), load_mapping(tmp_path / "m.yaml")
    errors = [f for f in validate_against_mapping(schema, bundle) if f.severity == "error"]
    offending = [f for f in errors if "not supported" in f.message]
    assert offending, errors
    assert "entities[Docs]" in offending[0].message
    assert "List" in offending[0].message, "the message must name the supported shape"


def test_a_list_declaring_a_non_generic_base_template_is_refused(tmp_path: Path) -> None:
    """The refusal above says "model the metadata as a 'List'". An author who
    changes only `kind` and leaves `base_template: 101` behind got a GREEN
    build that provisioned a real document library: the create body sends
    BaseTemplate and never `kind`, while every library guard in the build
    keys on `kind` and so does not fire.

    Checked as an allowlist rather than a denylist on 101. `base_template` is
    an unconstrained int taken straight from YAML, so a denylist would close
    one integer and leave 109, 119, 851 and the rest one keystroke from the
    same defect. This states what the tool builds, which needs no claim about
    SharePoint: every declaration in the repo is 100.
    """
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Docs {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar [not null]\n"
        "}\n",
        encoding="utf-8",
    )
    for template in (101, 109, 119):
        (tmp_path / "m.yaml").write_text(
            'prefix: "APP_"\n'
            "entities:\n"
            f"  Docs: {{ kind: List, base_template: {template}, site_role: default }}\n",
            encoding="utf-8",
        )
        schema = parse_dbml(tmp_path / "s.dbml")
        bundle = load_mapping(tmp_path / "m.yaml")
        errors = [
            f for f in validate_against_mapping(schema, bundle) if f.severity == "error"
        ]
        assert any(
            "entities[Docs]" in f.message and str(template) in f.message for f in errors
        ), f"base_template {template} was accepted: {errors}"


def test_a_document_library_reports_the_kind_not_the_base_template(tmp_path: Path) -> None:
    """The two checks are one `elif`, so `kind: DocumentLibrary` with its
    matching 101 gets the message that explains the actual problem rather
    than a second one about the integer it was always going to carry."""
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Docs {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar [not null]\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Docs: { kind: DocumentLibrary, base_template: 101, site_role: default }\n",
        encoding="utf-8",
    )
    schema, bundle = parse_dbml(tmp_path / "s.dbml"), load_mapping(tmp_path / "m.yaml")
    errors = [f for f in validate_against_mapping(schema, bundle) if f.severity == "error"]
    about_entity = [f for f in errors if "entities[Docs]" in f.message]
    assert len(about_entity) == 1, about_entity
    assert "DocumentLibrary" in about_entity[0].message


# --- Declared view totals ---------------------------------------------------


def test_a_total_on_a_column_the_view_does_not_show_is_refused(tmp_path: Path) -> None:
    """The widths failure shape exactly: SharePoint accepts the property and
    renders nothing, because the view has no column to put a figure under."""
    errors = _view_errors(
        tmp_path,
        "views:\n"
        "  Project:\n"
        "    - title: V\n"
        "      fields: [Title]\n"
        "      totals: { SortOrder: sum }\n",
    )
    assert any("SortOrder" in f.message and "totals" in f.message for f in errors), errors


def test_summing_a_choice_column_is_refused_and_points_at_count(tmp_path: Path) -> None:
    errors = _view_errors(
        tmp_path,
        "views:\n"
        "  Project:\n"
        "    - title: V\n"
        "      fields: [Title, Status]\n"
        "      totals: { Status: sum }\n",
    )
    assert any(
        "Status" in f.message and "count" in f.message for f in errors
    ), errors


def test_counting_a_choice_column_is_allowed(tmp_path: Path) -> None:
    """count counts ROWS, not values, so it is legal on any displayed
    column — which is why it is excluded from the numeric-only set rather
    than sharing the numeric rule."""
    errors = _view_errors(
        tmp_path,
        "views:\n"
        "  Project:\n"
        "    - title: V\n"
        "      fields: [Title, Status]\n"
        "      totals: { Status: count }\n",
    )
    assert not [f for f in errors if "totals" in f.message], errors


def test_summing_a_numeric_column_is_allowed(tmp_path: Path) -> None:
    errors = _view_errors(
        tmp_path,
        "views:\n"
        "  Project:\n"
        "    - title: V\n"
        "      fields: [Title, SortOrder]\n"
        "      totals: { SortOrder: sum }\n",
    )
    assert not [f for f in errors if "totals" in f.message], errors


def test_a_total_on_a_calculated_number_is_allowed(tmp_path: Path) -> None:
    """Three of the columns this feature exists for are calculated
    day-counts. The `string;#` prefix that complicates calculated TEXT is a
    column-formatting concern and never reaches a view's Aggregations."""
    schema, bundle = _calculated_form_inputs(
        tmp_path,
        "views:\n"
        "  Project:\n"
        "    - title: V\n"
        "      fields: [Title, Score]\n"
        "      totals: { Score: avg }\n",
    )
    errors = [f for f in validate_against_mapping(schema, bundle) if f.severity == "error"]
    assert not [f for f in errors if "totals" in f.message], errors


def _hyperlink_demo(tmp_path: Path, value: str) -> list[Finding]:
    """A whole build's worth of validation, not `_field_plan` alone: the
    demo planner and the demo VALIDATOR are separate readers of the same
    authored value, and a form one accepts and the other refuses never
    reaches generation."""
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Doc {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar [not null]\n"
        "  Link hyperlink\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Doc: { kind: List, base_template: 100, site_role: default }\n"
        "demo_items:\n"
        "  Doc:\n"
        "    - key: d1\n"
        "      values:\n"
        '        Title: "[DEMO] A row"\n'
        f"        Link: {value}\n",
        encoding="utf-8",
    )
    schema, bundle = parse_dbml(tmp_path / "s.dbml"), load_mapping(tmp_path / "m.yaml")
    return [f for f in validate_against_mapping(schema, bundle) if f.severity == "error"]


def test_a_hyperlink_demo_value_may_be_a_bare_url(tmp_path: Path) -> None:
    assert not _hyperlink_demo(tmp_path, '"https://example.invalid/a.pdf"')


def test_a_hyperlink_demo_value_may_carry_a_description(tmp_path: Path) -> None:
    """The object form the demo planner accepts. The validator must accept
    it too — it reads every dict, and a lookup reference is not the only
    thing that is one."""
    assert not _hyperlink_demo(
        tmp_path, '{ url: "https://example.invalid/a.pdf", description: "The file" }',
    )


def test_a_hyperlink_demo_object_needs_a_url(tmp_path: Path) -> None:
    errors = _hyperlink_demo(tmp_path, '{ description: "no address" }')
    assert any("url" in f.message for f in errors), errors


def test_a_hyperlink_demo_object_refuses_unknown_keys(tmp_path: Path) -> None:
    errors = _hyperlink_demo(
        tmp_path, '{ url: "https://example.invalid/a.pdf", label: "wrong key" }',
    )
    assert any("label" in f.message for f in errors), errors


def test_a_null_hyperlink_url_is_refused(tmp_path: Path) -> None:
    """`str(None)` is "None" — non-empty, and a perfectly valid-looking
    string. A coerced emptiness test passes it through to become a link
    pointing at the word None, so the check is on the STRING, not on its
    stringification."""
    errors = _hyperlink_demo(tmp_path, "{ url: null }")
    assert any("non-empty string" in f.message for f in errors), errors


def test_an_empty_hyperlink_url_is_refused(tmp_path: Path) -> None:
    errors = _hyperlink_demo(tmp_path, '{ url: "   " }')
    assert any("non-empty string" in f.message for f in errors), errors


def test_a_scalar_hyperlink_demo_value_is_validated_too(tmp_path: Path) -> None:
    """A URL column takes a bare address as well as a record. Checking only
    the record shape left `Link: null` and `Link: 123` unvalidated — and the
    generator refuses both, so the build surfaced a traceback instead of a
    finding. A validator must refuse everything its generator refuses."""
    for bad in ("null", "123", '""'):
        errors = _hyperlink_demo(tmp_path, bad)
        assert any("non-empty string" in f.message for f in errors), (bad, errors)


def test_names_that_differ_only_in_case_are_refused(tmp_path: Path) -> None:
    """SharePoint resolves group, permission-level and view names
    case-insensitively and will not hold two that differ only in case. A
    build that permits both produces a deploy that creates the first and
    collides on the second, mid-run, after the site has already changed.

    Caught here so the collision is a build error rather than a half-applied
    paste.
    """
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Project {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar [not null]\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Project: { kind: List, base_template: 100, site_role: default }\n"
        "permission_levels:\n"
        '  - { name: "APP Reader", description: "d", base_permissions: [ViewListItems] }\n'
        '  - { name: "app reader", description: "d", base_permissions: [ViewListItems] }\n'
        "groups:\n"
        '  - { name: "APP Owners", description: "d", owner_group: "Site Owners" }\n'
        '  - { name: "app owners", description: "d", owner_group: "Site Owners" }\n'
        "views:\n"
        "  Project:\n"
        "    - { title: Open, fields: [Title], default: true }\n"
        "    - { title: open, fields: [Title] }\n",
        encoding="utf-8",
    )
    schema, bundle = parse_dbml(tmp_path / "s.dbml"), load_mapping(tmp_path / "m.yaml")
    errors = [f for f in validate_against_mapping(schema, bundle) if f.severity == "error"]
    for what in ("permission_levels", "groups", "views"):
        assert any(
            f.message.startswith(what) and "case" in f.message for f in errors
        ), (what, [f.message for f in errors])


def test_a_lookup_targets_display_column_counts_as_an_index(tmp_path: Path) -> None:
    """The picker's index is real and spends a real slot, so the ceiling must
    see it. Declaring 20 and needing a 21st has to fail at validate time, not at
    deploy time on someone's tenant."""
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Event {\n"
        "  Id int [pk, increment]\n"
        "  Status nvarchar\n"
        "}\n"
        "Table FollowUp {\n"
        "  Id int [pk, increment]\n"
        "  Event int [ref: > Event.Id]\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Event: { kind: List, base_template: 100, site_role: default }\n"
        "  FollowUp: { kind: List, base_template: 100, site_role: default }\n",
        encoding="utf-8",
    )
    from dbml_sharepoint.analysis.checks._context import ValidationContext

    vc = ValidationContext.build(
        parse_dbml(tmp_path / "s.dbml"), load_mapping(tmp_path / "m.yaml"),
    )
    assert "Title" in vc.effective_indexes("Event")
    # The child is not a target of anything.
    assert vc.effective_indexes("FollowUp") == set()


def _cross_site_only_target(tmp_path: Path, *, calculated: bool) -> tuple[Schema, MappingBundle]:
    """FlowRunLog is pointed at by exactly one ref, and that ref is cross-site."""
    display = "  Label calculated_text\n" if calculated else "  Label nvarchar\n"
    formulas = (
        "calculated_formulas:\n  FlowRunLog:\n    Label: \"=[Title]\"\n"
        if calculated else ""
    )
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table FlowRunLog {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar\n"
        + display +
        "}\n"
        "Table Request {\n"
        "  Id int [pk, increment]\n"
        "  Origin int [ref: > FlowRunLog.Id]\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  FlowRunLog: { kind: List, base_template: 100, site_role: default, "
        "display_column: Label }\n"
        "  Request: { kind: List, base_template: 100, site_role: default }\n"
        "cross_site_reference_columns:\n"
        "  - { entity: Request, column: Origin }\n"
        + formulas,
        encoding="utf-8",
    )
    return parse_dbml(tmp_path / "s.dbml"), load_mapping(tmp_path / "m.yaml")


def test_a_cross_site_only_target_spends_no_index(tmp_path: Path) -> None:
    """A cross-site ref becomes a Choice + URL pair on the SOURCE list. Nothing
    enumerates FlowRunLog, so it has no picker — charging it an index would spend
    one of its twenty on a query that never happens."""
    from dbml_sharepoint.analysis.checks._context import ValidationContext

    schema, bundle = _cross_site_only_target(tmp_path, calculated=False)
    vc = ValidationContext.build(schema, bundle)
    assert vc.effective_indexes("FlowRunLog") == set()


def test_a_cross_site_only_target_is_not_told_its_picker_breaks(
    tmp_path: Path,
) -> None:
    """The warning claims 'this list's lookup picker stops working'. Said about a
    list with no picker it is simply false, and the author's only way to silence
    it is to accept a consequence that cannot occur."""
    schema, bundle = _cross_site_only_target(tmp_path, calculated=True)
    assert not [
        f for f in validate_against_mapping(schema, bundle)
        if "display_column" in f.message and "FlowRunLog" in f.message
    ], [f.message for f in validate_against_mapping(schema, bundle)]


def test_a_target_of_both_ref_kinds_keeps_its_index(tmp_path: Path) -> None:
    """Per-pair, not per-entity. Excluding every entity NAMED in
    cross_site_reference_columns would strip the index off a list whose picker is
    real, which is the same defect pointing the other way."""
    from dbml_sharepoint.analysis.checks._context import ValidationContext

    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table FlowRunLog {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar\n"
        "}\n"
        "Table Request {\n"
        "  Id int [pk, increment]\n"
        "  Origin int [ref: > FlowRunLog.Id]\n"
        "}\n"
        "Table Alert {\n"
        "  Id int [pk, increment]\n"
        "  Source int [ref: > FlowRunLog.Id]\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  FlowRunLog: { kind: List, base_template: 100, site_role: default }\n"
        "  Request: { kind: List, base_template: 100, site_role: default }\n"
        "  Alert: { kind: List, base_template: 100, site_role: default }\n"
        "cross_site_reference_columns:\n"
        "  - { entity: Request, column: Origin }\n",
        encoding="utf-8",
    )
    vc = ValidationContext.build(
        parse_dbml(tmp_path / "s.dbml"), load_mapping(tmp_path / "m.yaml"),
    )
    assert vc.effective_indexes("FlowRunLog") == {"Title"}


def test_a_calculated_display_column_does_not_count_as_an_index(tmp_path: Path) -> None:
    """It cannot be indexed, so counting it would push a schema over the ceiling
    for an index that cannot exist — the failure mode in the other direction."""
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Event {\n"
        "  Id int [pk, increment]\n"
        "  Ref nvarchar\n"
        "  Label calculated_text\n"
        "}\n"
        "Table FollowUp {\n"
        "  Id int [pk, increment]\n"
        "  Event int [ref: > Event.Id]\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Event: { kind: List, base_template: 100, site_role: default, "
        "display_column: Label }\n"
        "  FollowUp: { kind: List, base_template: 100, site_role: default }\n",
        encoding="utf-8",
    )
    from dbml_sharepoint.analysis.checks._context import ValidationContext

    vc = ValidationContext.build(
        parse_dbml(tmp_path / "s.dbml"), load_mapping(tmp_path / "m.yaml"),
    )
    assert "Label" not in vc.effective_indexes("Event")


_SHAPE_SCHEMA = (
    "Project t { database_type: 'SharePoint Online' }\n"
    "Table Job {\n"
    "  Id int [pk, increment]\n"
    "  Title nvarchar\n"
    "  Status nvarchar\n"
    "  DueDate date\n"
    "  indexes { Status }\n"
    "}\n"
)


def _shape_warnings(tmp_path: Path, where: str) -> list[str]:
    (tmp_path / "s.dbml").write_text(_SHAPE_SCHEMA, encoding="utf-8")
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Job: { kind: List, base_template: 100, site_role: default }\n"
        "views:\n"
        "  Job:\n"
        "    - title: V\n"
        "      fields: [Title, Status, DueDate]\n" + where,
        encoding="utf-8",
    )
    return [
        f.message
        for f in validate_against_mapping(
            parse_dbml(tmp_path / "s.dbml"), load_mapping(tmp_path / "m.yaml"),
        )
        if "list view threshold" in f.message
    ]


def test_an_or_needs_every_branch_indexed(tmp_path: Path) -> None:
    """An OR cannot narrow to one index. A row matching only the unindexed
    branch is still a row SharePoint has to find, so an indexed branch beside
    an unindexed one buys nothing — and scoring it safe because SOME filtered
    column is indexed is how a scanning view passes validation."""
    assert len(_shape_warnings(
        tmp_path,
        "      where:\n"
        "        any_of:\n"
        "          - { field: Status, op: eq, value: Open }\n"
        "          - { field: DueDate, op: leq, value: today }\n",
    )) == 1


def test_an_or_with_every_branch_indexed_is_quiet(tmp_path: Path) -> None:
    """Both branches narrow, so neither forces a scan."""
    assert _shape_warnings(
        tmp_path,
        "      where:\n"
        "        any_of:\n"
        "          - { field: Status, op: eq, value: Open }\n"
        "          - { field: Status, op: eq, value: Held }\n",
    ) == []


def test_an_and_needs_only_one_branch_indexed(tmp_path: Path) -> None:
    """Measured at 6,000 items: an unindexed comparison refused on its own is
    served when ANDed with an indexed one, in either order — SharePoint picks
    the index rather than taking the first column and stopping. So an AND is
    covered by one indexed condition wherever it sits, and this test is what
    stops the OR rule above being applied to both."""
    assert _shape_warnings(
        tmp_path,
        "      where:\n"
        "        - { field: Status, op: eq, value: Open }\n"
        "        - { field: DueDate, op: leq, value: today }\n",
    ) == []


# --- View join threshold (the list view LOOKUP threshold, not the item count) ---


def _persons(count: int) -> str:
    """`count` person columns, P1..Pn — the cheapest join-bearing column."""
    return "".join(f"  P{n} person\n" for n in range(1, count + 1))


def _join_inputs(
    tmp_path: Path, columns: str, mapping_tail: str = "",
) -> tuple[Schema, MappingBundle]:
    """A Project table whose extra columns the caller supplies, so a test can
    put an exact number of join-bearing columns on it. `mapping_tail` is
    appended inside the Project entity block — indent it four spaces to add an
    entity key, or start at column zero to open a new top-level section."""
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Person {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar [not null]\n"
        "}\n"
        "Table Project {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar [not null]\n"
        "  Notes nvarchar\n"
        f"{columns}"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Person: { kind: List, base_template: 100, site_role: default }\n"
        "  Project:\n"
        "    kind: List\n"
        "    base_template: 100\n"
        "    site_role: default\n"
        + mapping_tail,
        encoding="utf-8",
    )
    return parse_dbml(tmp_path / "s.dbml"), load_mapping(tmp_path / "m.yaml")


def _join_findings(
    schema: Schema, bundle: MappingBundle, subject: str,
) -> list[Finding]:
    """Join-threshold findings about one subject.

    Both substrings are required. 'join-bearing columns' and 'join operations'
    occur together in no other message in this codebase, so if the check is
    deleted this returns [] and every assertion below fails — while the
    unnecessary-suppression warning added in Task 5, which also says
    'join-bearing columns', is excluded because it never says 'join
    operations'."""
    return [
        f for f in validate_against_mapping(schema, bundle)
        if "join-bearing columns" in f.message
        and "join operations" in f.message
        and f.message.startswith(subject)
    ]


def _named(message: str) -> list[str]:
    """The columns a join finding NAMES, taken from its parenthesised list.

    Assert against this, never against the whole message, whenever a test cares
    whether a column name is present or absent. `_join_finding` appends a shared
    sentence reading "...including Created By (Author) and Modified By (Editor);
    Created and Modified cost nothing...", so `"Created" not in f.message` and
    `"Author" in f.message` are BOTH vacuous — the first can never pass and the
    second passes even if the column was never counted. The parenthesised list is
    the only part of the message that varies with the count.

    The first "(" in every join finding opens that list: the subject prefixes
    (`views[X].Y:` and `entities[X]: the generated 'All Items' view`) use
    brackets and quotes, never parentheses."""
    return message.split("(", 1)[1].split(")", 1)[0].split(", ")


def _view_block(title: str, fields: list[str]) -> str:
    return (
        "views:\n"
        "  Project:\n"
        f"    - title: {title}\n"
        f"      fields: [{', '.join(fields)}]\n"
    )


def test_a_view_with_eight_join_columns_is_silent(tmp_path: Path) -> None:
    """Under every figure ever documented, anywhere. The subject filter matters:
    this entity's generated All Items carries 10 and is warned about separately."""
    schema, bundle = _join_inputs(
        tmp_path,
        _persons(8),
        _view_block("Wide", ["Title", *(f"P{n}" for n in range(1, 9))]),
    )
    assert _join_findings(schema, bundle, "views[Project].Wide") == []


def test_a_view_with_nine_join_columns_warns(tmp_path: Path) -> None:
    schema, bundle = _join_inputs(
        tmp_path,
        _persons(9),
        _view_block("Wide", ["Title", *(f"P{n}" for n in range(1, 10))]),
    )
    found = _join_findings(schema, bundle, "views[Project].Wide")
    assert len(found) == 1
    assert found[0].severity == "warning"
    assert "9 join-bearing columns" in found[0].message
    assert "P9" in _named(found[0].message)
    assert "Remove fields from this view." in found[0].message


def test_a_view_with_thirteen_join_columns_errors(tmp_path: Path) -> None:
    schema, bundle = _join_inputs(
        tmp_path,
        _persons(13),
        _view_block("Wide", ["Title", *(f"P{n}" for n in range(1, 14))]),
    )
    found = _join_findings(schema, bundle, "views[Project].Wide")
    assert len(found) == 1
    assert found[0].severity == "error"
    assert "13 join-bearing columns" in found[0].message
    assert "-2147024749" in found[0].message
    assert "Remove fields from this view." in found[0].message


def test_author_and_editor_each_cost_a_join_and_the_dates_cost_none(
    tmp_path: Path,
) -> None:
    """The pairing is the whole point: the same 12 columns pass, and adding one
    system PERSON column fails while adding two system DATES does not.

    Every name assertion goes through `_named`. Asserted against the whole
    message they would all be vacuous — the shared sentence `_join_finding`
    appends says "including Created By (Author) and Modified By (Editor); Created
    and Modified cost nothing", so "Created"/"Modified"/"Author" are in EVERY
    join message regardless of what was counted."""
    twelve = [f"P{n}" for n in range(1, 13)]

    schema, bundle = _join_inputs(
        tmp_path, _persons(12),
        _view_block("Dates", ["Title", *twelve, "Created", "Modified"]),
    )
    dates = _join_findings(schema, bundle, "views[Project].Dates")
    assert len(dates) == 1
    assert dates[0].severity == "warning"
    assert "12 join-bearing columns" in dates[0].message
    assert "Created" not in _named(dates[0].message)
    assert "Modified" not in _named(dates[0].message)

    schema, bundle = _join_inputs(
        tmp_path, _persons(12), _view_block("WithAuthor", ["Title", *twelve, "Author"]),
    )
    with_author = _join_findings(schema, bundle, "views[Project].WithAuthor")
    assert len(with_author) == 1
    assert with_author[0].severity == "error"
    assert "13 join-bearing columns" in with_author[0].message
    assert "Author" in _named(with_author[0].message)

    schema, bundle = _join_inputs(
        tmp_path, _persons(12), _view_block("WithEditor", ["Title", *twelve, "Editor"]),
    )
    with_editor = _join_findings(schema, bundle, "views[Project].WithEditor")
    assert len(with_editor) == 1
    assert with_editor[0].severity == "error"
    assert "13 join-bearing columns" in with_editor[0].message
    assert "Editor" in _named(with_editor[0].message)


def test_a_real_ref_column_costs_a_join(tmp_path: Path) -> None:
    """The control for the cross-site test below. The schema is identical; the
    view must name the expanded pair rather than the column, because a cross-site
    column never exists under its own name (validator.py:145-147). The COUNT is
    what is being compared: 13 here, 12 there."""
    twelve = [f"P{n}" for n in range(1, 13)]
    schema, bundle = _join_inputs(
        tmp_path,
        _persons(12) + "  Elsewhere int [ref: > Person.Id]\n",
        _view_block("Wide", ["Title", *twelve, "Elsewhere"]),
    )
    found = _join_findings(schema, bundle, "views[Project].Wide")
    assert len(found) == 1
    assert found[0].severity == "error"
    assert "13 join-bearing columns" in found[0].message
    assert "Elsewhere" in _named(found[0].message)


def test_a_cross_site_ref_costs_no_join_in_a_view(tmp_path: Path) -> None:
    twelve = [f"P{n}" for n in range(1, 13)]
    schema, bundle = _join_inputs(
        tmp_path,
        _persons(12) + "  Elsewhere int [ref: > Person.Id]\n",
        _view_block(
            "Wide",
            ["Title", *twelve, "ElsewhereAbbreviation", "ElsewhereSiteUrl"],
        )
        + "cross_site_reference_columns:\n"
        "  - { entity: Project, column: Elsewhere }\n",
    )
    found = _join_findings(schema, bundle, "views[Project].Wide")
    assert len(found) == 1
    assert found[0].severity == "warning"
    assert "12 join-bearing columns" in found[0].message
    assert "Elsewhere" not in _named(found[0].message)


def test_a_view_declaring_a_field_set_counts_the_join_columns_it_expands_to(
    tmp_path: Path,
) -> None:
    """Sets are expanded into ViewDef.fields at load time. A view whose authored
    fields is ["@wide"] must count what @wide resolves to, not zero.

    NAMED with "join" in it on purpose. The earlier name
    `..._is_counted_on_its_expansion` contained no "join", so `-k join` never
    collected it and the step that was meant to watch it fail first ran five
    words of nothing."""
    thirteen = ", ".join(f"P{n}" for n in range(1, 14))
    schema, bundle = _join_inputs(
        tmp_path,
        _persons(13),
        "field_sets:\n"
        "  Project:\n"
        f"    wide: [{thirteen}]\n"
        "views:\n"
        "  Project:\n"
        "    - title: Wide\n"
        '      fields: [Title, "@wide"]\n',
    )
    found = _join_findings(schema, bundle, "views[Project].Wide")
    assert len(found) == 1
    assert found[0].severity == "error"
    assert "13 join-bearing columns" in found[0].message


def test_a_declared_view_counts_every_join_it_declares_even_when_hidden(
    tmp_path: Path,
) -> None:
    """`hide_from_all_items` must not reach the DECLARED-view count.

    The generator-side half of this rule is tested in test_jsgen.py; this is the
    VALIDATOR-side half, and without it a plausible 'consistency' edit — both
    derivations sit in the same entity loop, so subtracting `all_items_hidden`
    from the per-view count looks tidy — would quietly stop erroring on a view
    over 13 join columns with the whole suite still green.

    13, not 11: P1 and P2 are hidden from All Items and the declared view keeps
    them."""
    schema, bundle = _join_inputs(
        tmp_path,
        _persons(13),
        "    hide_from_all_items: [P1, P2]\n"
        + _view_block("Wide", ["Title", *(f"P{n}" for n in range(1, 14))]),
    )
    found = _join_findings(schema, bundle, "views[Project].Wide")
    assert len(found) == 1
    assert found[0].severity == "error"
    assert "13 join-bearing columns" in found[0].message
    assert "P1" in _named(found[0].message)
    assert "P2" in _named(found[0].message)


def test_the_generated_all_items_counts_author_and_editor_as_joins(
    tmp_path: Path,
) -> None:
    """11 declared join columns + Author + Editor = 13. Nothing declares this
    view — the generator appends both system columns unconditionally — so the
    message has to name all three contributions and point at the only remedy.

    All three name assertions go through `_named`. Against the whole message
    "Author" and "Editor" would pass even if SYSTEM_JOIN_COLUMNS were EMPTY and
    neither column were counted, because `_join_finding`'s shared sentence says
    "Created By (Author) and Modified By (Editor)" in every finding it makes."""
    schema, bundle = _join_inputs(tmp_path, _persons(11))
    found = _join_findings(schema, bundle, "entities[Project]")
    assert len(found) == 1
    assert found[0].severity == "error"
    assert "13 join-bearing columns" in found[0].message
    names = _named(found[0].message)
    assert "Author" in names
    assert "Editor" in names
    assert "P11" in names
    assert "hide_from_all_items" in found[0].message
    # The declared-view remedy must NOT be offered: All Items cannot be edited.
    assert "Remove fields from this view." not in found[0].message


def test_the_generated_all_items_join_count_is_silent_under_the_band(
    tmp_path: Path,
) -> None:
    """The negative case: 6 declared + Author + Editor = 8, under the band."""
    schema, bundle = _join_inputs(tmp_path, _persons(6))
    assert _join_findings(schema, bundle, "entities[Project]") == []


def test_the_generated_all_items_starts_at_two_joins(tmp_path: Path) -> None:
    """Author and Editor are 2 of the 12 before a single business column, so an
    entity's real budget for its own columns is 10. 7 declared columns is 9."""
    schema, bundle = _join_inputs(tmp_path, _persons(7))
    found = _join_findings(schema, bundle, "entities[Project]")
    assert len(found) == 1
    assert found[0].severity == "warning"
    assert "9 join-bearing columns" in found[0].message


def test_hide_from_all_items_clears_the_all_items_join_error(
    tmp_path: Path,
) -> None:
    schema, bundle = _join_inputs(
        tmp_path, _persons(11), "    hide_from_all_items: [Author, Editor]\n",
    )
    found = _join_findings(schema, bundle, "entities[Project]")
    assert [f for f in found if f.severity == "error"] == []
    # 11 remain, which is inside the 9-12 band, so the warning legitimately
    # stays. The key raises the ceiling on what an ENTITY may carry; it does
    # not remove the limit on what a VIEW may render.
    assert len(found) == 1
    assert found[0].severity == "warning"
    assert "11 join-bearing columns" in found[0].message
    assert "Author" not in _named(found[0].message)
    assert "Editor" not in _named(found[0].message)


def test_hide_from_all_items_does_not_lift_the_join_ceiling(
    tmp_path: Path,
) -> None:
    """The spec's fourth validation rule, and the one an implementation can pass
    the rest of this suite while breaking: "After suppression, the >=13 error
    still applies. The key raises the ceiling on what an ENTITY may carry; it
    does not remove the limit on what a VIEW may render."

    Without this, an implementation that computed `shown_joins` on `rendered`
    only when `hidden` is empty — or that skipped the band check whenever
    `hide_from_all_items` is set — passes every other test in the plan. The
    clears-the-error test above only proves suppression can make a finding go
    away; nothing else proves INSUFFICIENT suppression still errors.

    14 persons + Author + Editor = 16; Author and Editor are hidden; 14 remain,
    which is still over 12."""
    schema, bundle = _join_inputs(
        tmp_path, _persons(14), "    hide_from_all_items: [Author, Editor]\n",
    )
    found = _join_findings(schema, bundle, "entities[Project]")
    assert len(found) == 1
    assert found[0].severity == "error"
    assert "14 join-bearing columns" in found[0].message
    assert "Author" not in _named(found[0].message)
    assert "Editor" not in _named(found[0].message)
    assert "hide_from_all_items" in found[0].message


def test_a_document_library_gets_no_all_items_join_finding(
    tmp_path: Path,
) -> None:
    """The `kind == "DocumentLibrary"` half of the loop guard, PAIRED.

    `jsgen.py:596` builds `All Items` only when the kind is not
    `DocumentLibrary`, so counting one here would refuse a schema over a view
    the generator never creates — the exact validator/generator disagreement
    this module exists to avoid. Deleting the clause must turn a test red, and
    only the pair does that: the count alone proves nothing, because the same
    13 columns are what the List case is asserted on.

    `kind: DocumentLibrary` is separately an ERROR from `_structure.py:101-111`,
    so this build is already red for another reason. That is not a licence to
    skip the guard — it is why the guard is easy to delete unnoticed."""
    library = (
        'prefix: "APP_"\n'
        "entities:\n"
        "  Person: { kind: List, base_template: 100, site_role: default }\n"
        "  Project:\n"
        "    kind: DocumentLibrary\n"
        "    base_template: 100\n"
        "    site_role: default\n"
    )
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Person {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar [not null]\n"
        "}\n"
        "Table Project {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar [not null]\n"
        f"{_persons(13)}"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(library, encoding="utf-8")
    schema = parse_dbml(tmp_path / "s.dbml")
    bundle = load_mapping(tmp_path / "m.yaml")
    assert _join_findings(schema, bundle, "entities[Project]") == []

    # The pair. The identical schema declared `kind: List` DOES error, so the
    # empty result above is the guard and not an accident of the fixture.
    as_list, as_list_bundle = _join_inputs(tmp_path, _persons(13))
    found = _join_findings(as_list, as_list_bundle, "entities[Project]")
    assert len(found) == 1
    assert found[0].severity == "error"
    assert "15 join-bearing columns" in found[0].message


def test_hide_from_all_items_on_a_document_library_is_refused(
    tmp_path: Path,
) -> None:
    """The refusal above the loop's `continue`, exercised for the first time in
    this file. No other test in this section supplies `hide_from_all_items` on
    an entity the loop skips, so without this the branch that answers it has
    no red/green cycle anywhere in the suite — the `_join_findings` filter
    would not even see it, since this message never says "join-bearing
    columns" or "join operations": it belongs to a different subject entirely.

    Task 5's own covering test for this branch is already green at its
    fail-first gate, by design, because Task 4 answers this key before Task 5
    exists — that is documented there, not a gap here."""
    library = (
        'prefix: "APP_"\n'
        "entities:\n"
        "  Person: { kind: List, base_template: 100, site_role: default }\n"
        "  Project:\n"
        "    kind: DocumentLibrary\n"
        "    base_template: 100\n"
        "    site_role: default\n"
        "    hide_from_all_items: [Author]\n"
    )
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Person {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar [not null]\n"
        "}\n"
        "Table Project {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar [not null]\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(library, encoding="utf-8")
    schema = parse_dbml(tmp_path / "s.dbml")
    bundle = load_mapping(tmp_path / "m.yaml")
    found = [
        f for f in validate_against_mapping(schema, bundle)
        if f.message.startswith("entities[Project].hide_from_all_items")
    ]
    assert len(found) == 1
    assert found[0].severity == "error"


def test_a_cross_site_ref_costs_no_join_on_all_items(tmp_path: Path) -> None:
    """A cross-site column is rendered as a Choice + URL PAIR — two rendered
    columns — and still costs nothing. Paired with the control below."""
    schema, bundle = _join_inputs(
        tmp_path,
        _persons(10) + "  Elsewhere int [ref: > Person.Id]\n",
        "cross_site_reference_columns:\n"
        "  - { entity: Project, column: Elsewhere }\n",
    )
    found = _join_findings(schema, bundle, "entities[Project]")
    assert len(found) == 1
    assert found[0].severity == "warning"
    assert "12 join-bearing columns" in found[0].message

    # Control: the same column as a real ref makes it 13.
    schema, bundle = _join_inputs(
        tmp_path, _persons(10) + "  Elsewhere int [ref: > Person.Id]\n",
    )
    control = _join_findings(schema, bundle, "entities[Project]")
    assert len(control) == 1
    assert control[0].severity == "error"
    assert "13 join-bearing columns" in control[0].message


def _hide_errors(
    schema: Schema, bundle: MappingBundle, entity: str = "Project",
) -> list[str]:
    prefix = f"entities[{entity}].hide_from_all_items"
    return [
        f.message for f in validate_against_mapping(schema, bundle)
        if f.severity == "error" and f.message.startswith(prefix)
    ]


def test_hiding_a_column_all_items_does_not_render_errors(tmp_path: Path) -> None:
    """A typo must not silently do nothing."""
    schema, bundle = _join_inputs(
        tmp_path, _persons(11), "    hide_from_all_items: [Athor]\n",
    )
    msgs = _hide_errors(schema, bundle)
    assert len(msgs) == 1
    assert "'Athor'" in msgs[0]
    assert "not a column the generated 'All Items' view renders" in msgs[0]

    # Negative case: the correctly spelled column is accepted silently.
    schema, bundle = _join_inputs(
        tmp_path, _persons(11), "    hide_from_all_items: [Author]\n",
    )
    assert _hide_errors(schema, bundle) == []


# test_hiding_a_column_on_an_entity_with_no_all_items_errors is deliberately
# NOT duplicated here. Task 4's fix round already added
# test_hide_from_all_items_on_a_document_library_is_refused above, which
# exercises the identical branch — a hide_from_all_items key on a
# DocumentLibrary, refused above this loop's `continue` — and asserts exactly
# one "error" finding whose message starts with the same
# "entities[Project].hide_from_all_items" prefix. A second test asserting the
# same branch would be duplication, not coverage.


def test_hiding_a_column_that_costs_no_join_errors(tmp_path: Path) -> None:
    """All Items renders every column for a reason. The threshold is the one
    exception, not a general hide-this feature."""
    schema, bundle = _join_inputs(
        tmp_path, _persons(11), "    hide_from_all_items: [Notes]\n",
    )
    msgs = _hide_errors(schema, bundle)
    assert len(msgs) == 1
    assert "'Notes'" in msgs[0]
    assert "costs no join operation" in msgs[0]

    # Negative case: a person column on the same entity is hideable.
    schema, bundle = _join_inputs(
        tmp_path, _persons(11), "    hide_from_all_items: [P1]\n",
    )
    assert _hide_errors(schema, bundle) == []


def test_hiding_title_is_refused_as_not_join_bearing_not_as_a_typo(
    tmp_path: Path,
) -> None:
    """`hide_from_all_items: [Title]` must be refused for costing no join
    (nvarchar, not join-bearing), never reported as an unrecognised column:
    the wrong branch would send the author looking for a typo in a column
    that plainly exists.

    NOTE on what this test can and cannot pin, recorded here because it is
    not obvious from the assertions alone. `_join_inputs` declares `Title`
    as a real DBML column on `Project`, so `_rendered_columns` alone already
    puts 'Title' in `rendered` — the explicit `| {"Title"}` union inside
    `analysis/joins.py::all_items_rendered` is redundant for THIS fixture
    and this test cannot observe it being dropped. That is by design, not
    an oversight: this test pins the branch choice for an entity that DOES
    declare its own Title (a real, common case), and
    `test_hiding_an_undeclared_title_still_takes_the_not_join_bearing_branch`
    immediately below pins the case that actually exercises the union — see
    task-6-report.md, 'Fix round 2' and 'Fix round 3', for the investigation
    that separated the two.
    """
    schema, bundle = _join_inputs(
        tmp_path, _persons(11), "    hide_from_all_items: [Title]\n",
    )
    msgs = _hide_errors(schema, bundle)
    assert len(msgs) == 1
    assert "costs no join operation" in msgs[0]
    assert "Check the spelling" not in msgs[0]


def test_hiding_an_undeclared_title_still_takes_the_not_join_bearing_branch(
    tmp_path: Path,
) -> None:
    """The fixture `_join_inputs` builds cannot pin this — see the NOTE on
    `test_hiding_title_is_refused_as_not_join_bearing_not_as_a_typo` above.
    This entity's DBML declares NO `Title` column at all, which is legal:
    SharePoint's base-template `Title` exists on every provisioned list
    regardless of whether the schema names it. So 'Title' reaches
    `all_items_rendered`'s result ONLY through its `| {"Title"}` union —
    `_rendered_columns` alone has nothing to contribute for a column that
    is not in `table.columns`. `hide_from_all_items: [Title]` must still be
    refused for costing no join, not reported as an unrecognised column."""
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Project {\n"
        "  Id int [pk, increment]\n"
        "  Notes nvarchar\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Project:\n"
        "    kind: List\n"
        "    base_template: 100\n"
        "    site_role: default\n"
        "    hide_from_all_items: [Title]\n",
        encoding="utf-8",
    )
    schema = parse_dbml(tmp_path / "s.dbml")
    bundle = load_mapping(tmp_path / "m.yaml")
    msgs = _hide_errors(schema, bundle)
    assert len(msgs) == 1
    assert "costs no join operation" in msgs[0]
    assert "Check the spelling" not in msgs[0]


def test_hiding_a_cross_site_ref_errors(tmp_path: Path) -> None:
    """It is a `ref` in DBML but expands to Choice + URL, so it costs no join
    and hiding it buys nothing."""
    columns = _persons(11) + "  Elsewhere int [ref: > Person.Id]\n"
    schema, bundle = _join_inputs(
        tmp_path,
        columns,
        "    hide_from_all_items: [Elsewhere]\n"
        "cross_site_reference_columns:\n"
        "  - { entity: Project, column: Elsewhere }\n",
    )
    msgs = _hide_errors(schema, bundle)
    assert len(msgs) == 1
    assert "'Elsewhere'" in msgs[0]
    assert "is a cross-site reference" in msgs[0]

    # Negative case: the identical column, hidden identically, is fine once it
    # is a real Lookup. Only the cross_site_reference_columns entry differs.
    schema, bundle = _join_inputs(
        tmp_path, columns, "    hide_from_all_items: [Elsewhere]\n",
    )
    assert _hide_errors(schema, bundle) == []


def _unnecessary_hide_warnings(schema: Schema, bundle: MappingBundle) -> list[str]:
    return [
        f.message for f in validate_against_mapping(schema, bundle)
        if f.severity == "warning" and "hide_from_all_items is set, but" in f.message
    ]


def test_unnecessary_hide_from_all_items_warns(tmp_path: Path) -> None:
    """Mirrors the pointless-acceptance warning already shipped for
    accept_unindexable_display_column.

    THREE cases, because the condition is a band boundary at 12/13 and the
    boundary is where it breaks. Written `< JOIN_LIMIT` instead of `<=`, the
    check silently stops nagging the entity that most deserves it — 12
    unsuppressed joins with the key set for nothing — and a suite that only
    exercised 4 and 13 would stay green through it."""
    # Well inside: P1, P2, Author, Editor with nothing hidden.
    schema, bundle = _join_inputs(
        tmp_path, _persons(2), "    hide_from_all_items: [Author]\n",
    )
    msgs = _unnecessary_hide_warnings(schema, bundle)
    assert len(msgs) == 1
    assert "renders 4 join-bearing columns with nothing hidden" in msgs[0]
    assert "Remove it" in msgs[0]

    # ON the boundary: 10 persons + Author + Editor = 12 unsuppressed, which is
    # exactly JOIN_LIMIT, so the key was not needed and this MUST still warn.
    schema, bundle = _join_inputs(
        tmp_path, _persons(10), "    hide_from_all_items: [Author]\n",
    )
    msgs = _unnecessary_hide_warnings(schema, bundle)
    assert len(msgs) == 1
    assert "renders 12 join-bearing columns with nothing hidden" in msgs[0]

    # Negative case, one past the boundary: 11 + Author + Editor = 13
    # unsuppressed. The entity genuinely needs the key and is not nagged.
    schema, bundle = _join_inputs(
        tmp_path, _persons(11), "    hide_from_all_items: [Author, Editor]\n",
    )
    assert _unnecessary_hide_warnings(schema, bundle) == []
