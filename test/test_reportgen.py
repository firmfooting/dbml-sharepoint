# test/test_reportgen.py
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest
from _model import bundle as make_bundle
from _model import column
from _model import enum as make_enum
from _model import schema as make_schema
from _model import table as make_table
from _paths import FIXTURES

from dbml_sharepoint.analysis.typemap import FieldKind, SPField, map_column
from dbml_sharepoint.generators import reportgen
from dbml_sharepoint.generators.reportgen import (
    generate_data_dictionary,
    generate_dictionary_powerquery,
    generate_dictionary_sql,
    generate_powerquery,
    generate_reporting_md,
    generate_sql_views,
)
from dbml_sharepoint.model.conditions import Group, Leaf
from dbml_sharepoint.model.mapping_loader import (
    ColumnValidation,
    EntitySection,
    FormVisibility,
    MappingBundle,
    load_mapping,
)
from dbml_sharepoint.model.parser import Column, Schema, TableIndex, parse_dbml
from dbml_sharepoint.model.release import load_release


def _simple() -> tuple[Schema, MappingBundle]:
    return (
        parse_dbml(FIXTURES / "simple.dbml"),
        load_mapping(FIXTURES / "sharepoint-mapping.yaml"),
    )


def _calculated() -> tuple[Schema, MappingBundle]:
    return (
        parse_dbml(FIXTURES / "calculated.dbml"),
        load_mapping(FIXTURES / "calculated-mapping.yaml"),
    )


def test_powerquery_one_query_per_entity_with_odata_feed() -> None:
    schema, bundle = _simple()
    queries = generate_powerquery(schema, bundle, "default")
    assert set(queries) == {"APP_Project.pq", "APP_Task.pq", "APP_AppSettings.pq"}
    task = queries["APP_Task.pq"]
    assert "OData.Feed(" in task
    assert "getbytitle('APP_Task')" in task
    assert "SiteUrl &" in task  # parameterised, not hardcoded


def test_powerquery_lookup_selects_join_key_and_expands_title() -> None:
    schema, bundle = _simple()
    task = generate_powerquery(schema, bundle, "default")["APP_Task.pq"]
    # Join key comes back as the scalar <col>Id property...
    assert "ProjectId" in task
    # ...and the display title via $expand + record expansion.
    assert "$expand=Project" in task
    assert 'Table.ExpandRecordColumn' in task
    assert '"ProjectTitle"' in task


def test_powerquery_types_follow_the_schema() -> None:
    schema, bundle = _simple()
    task = generate_powerquery(schema, bundle, "default")["APP_Task.pq"]
    assert '{"DueDate", type date}' in task
    assert '{"Id", Int64.Type}' in task
    schema, bundle = _calculated()
    risk = generate_powerquery(schema, bundle, "default")["APP_Risk.pq"]
    assert '{"RiskScore", type number}' in risk  # calculated_number
    assert '{"RiskBand", type text}' in risk     # calculated_text


def test_sql_views_typed_and_enriched_with_joins() -> None:
    schema, bundle = _simple()
    sql = generate_sql_views(schema, bundle, "default")
    assert "CREATE OR ALTER VIEW" in sql
    assert "[vw_APP_Task]" in sql
    assert "[vw_APP_Task_Enriched]" in sql
    # The enriched view joins the lookup target on the Id key.
    assert "LEFT JOIN" in sql
    assert "[ProjectId]" in sql
    assert "AS [ProjectTitle]" in sql
    # Types projected from the schema.
    assert "CAST(t.[DueDate] AS DATE)" in sql
    # SQLCMD-parameterised schemas, not hardcoded.
    assert ":setvar LandingSchema" in sql
    assert "$(ReportSchema)" in sql


def test_reporting_md_lists_relationships_for_power_bi() -> None:
    """On the site-qualified Key columns, never on Id.

    `Id` is unique within one list on one site. A report that appends the
    same list from several sites has three different rows with Id = 1, so a
    relationship on Id degrades from many-to-one to many-to-many and joins
    each child to the same-numbered parent on every site -- rendering
    happily with wrong numbers.
    """
    schema, bundle = _simple()
    md = generate_reporting_md(schema, bundle, "default")
    assert "| APP_Task | Project Key | APP_Project | Project Key |" in md
    assert "| APP_Task | ProjectId | APP_Project | Id |" not in md
    assert "SiteUrl" in md  # parameter setup instructions


def test_every_list_query_carries_the_site_it_came_from() -> None:
    """Without these, an appended multi-site table has nothing to slice by."""
    schema, bundle = _simple()
    queries = generate_powerquery(schema, bundle, "default")
    for name, query in queries.items():
        assert '"Site Url", each SiteUrl' in query, name
        assert '"Site Name", each SiteName' in query, name


def test_the_site_name_is_read_from_the_site_not_configured() -> None:
    """The whole point: nobody maintains a URL-to-name list by hand, and a
    site renamed in SharePoint shows its new name at the next refresh.

    `_api/web?$select=Title` is documented on Microsoft Learn and was
    confirmed against a live tenant to answer with an OData entry carrying
    `d:Title` -- the shape `OData.Feed` consumes.
    """
    schema, bundle = _simple()
    task = generate_powerquery(schema, bundle, "default")["APP_Task.pq"]
    assert '"/_api/web?$select=Title"' in task


def test_each_query_resolves_its_own_site_name() -> None:
    """NOT a shared query, and this is the reason.

    A multi-site report is built by duplicating a list query per site and
    pointing each copy at a different URL. A single shared site-name query
    binds to ONE SiteUrl parameter, so every copy would be stamped with the
    first site's name -- wrong, and silently so, since the rows would be
    right and only the label wrong.

    Inline, the name is derived from whichever URL fetched the rows beside
    it, so a duplicate needs no edit beyond its site parameter.
    """
    schema, bundle = _simple()
    queries = generate_powerquery(schema, bundle, "default")
    assert not any(name.startswith("_Site") for name in queries)
    for name, query in queries.items():
        assert "SiteName =" in query, name
        assert '"/_api/web?$select=Title"' in query, name


def test_the_site_name_lookup_fails_soft() -> None:
    """A slicer label must not be able to take the refresh down.

    This is one of the few places the codebase should NOT fail closed: the
    rows are the data, the name is decoration, and an unhandled error here
    would fail every table in the report.
    """
    schema, bundle = _simple()
    task = generate_powerquery(schema, bundle, "default")["APP_Task.pq"]
    assert "try" in task
    assert "otherwise SiteUrl," in task


def test_row_keys_are_site_qualified() -> None:
    """`Id` alone collides the moment a second site is appended."""
    schema, bundle = _simple()
    task = generate_powerquery(schema, bundle, "default")["APP_Task.pq"]
    assert '"Task Key",' in task
    assert 'each SiteUrl & "|" & Number.ToText([Id])' in task


def test_a_null_lookup_does_not_break_the_refresh() -> None:
    """`Number.ToText(null)` raises rather than returning null, so an
    optional lookup left blank would fail the whole refresh."""
    schema, bundle = _simple()
    task = generate_powerquery(schema, bundle, "default")["APP_Task.pq"]
    assert "if [ProjectId] = null then null" in task


def test_report_respects_site_role_filter() -> None:
    """Entities outside the requested site role are not reported on."""
    schema, bundle = _simple()
    # All fixture entities are role 'default'; asking for another role
    # yields nothing rather than everything.
    assert generate_powerquery(schema, bundle, "admin") == {}


def test_powerquery_adds_itemurl_helper_column() -> None:
    schema, bundle = _simple()
    task = generate_powerquery(schema, bundle, "default")["APP_Task.pq"]
    assert "Table.AddColumn" in task
    assert '"ItemURL"' in task
    assert "/Lists/APP_Task/DispForm.aspx?ID=" in task


def test_sql_views_add_itemurl_helper_column() -> None:
    schema, bundle = _simple()
    sql = generate_sql_views(schema, bundle, "default")
    assert ":setvar SiteUrl" in sql
    assert "AS [ItemURL]" in sql
    assert "/Lists/APP_Task/DispForm.aspx?ID=" in sql


def test_data_dictionary_documents_every_list_and_column() -> None:
    schema, bundle = _simple()
    md = generate_data_dictionary(schema, bundle, "default")
    assert "## APP_Task" in md
    assert "| DueDate |" in md
    # Choice members come from the authoritative DBML enum.
    assert "Open" in md
    assert "Closed" in md
    # Lookup target and helper column are documented.
    assert "APP_Project" in md
    assert "ItemURL" in md


def test_data_dictionary_rejects_composite_indexes() -> None:
    schema, bundle = _simple()
    task = next(table for table in schema.tables if table.name == "Task")
    task.indexes = [TableIndex(("Project", "DueDate"))]
    with pytest.raises(ValueError, match="composite DBML indexes"):
        generate_data_dictionary(schema, bundle, "default")


def test_data_dictionary_includes_calculated_formulas() -> None:
    schema, bundle = _calculated()
    md = generate_data_dictionary(schema, bundle, "default")
    assert '=IF([Severity]="High",10,1)' in md


def test_data_dictionary_includes_deployment_metadata() -> None:
    schema, bundle = _simple()
    release = load_release(FIXTURES / "release.yaml")
    md = generate_data_dictionary(
        schema, bundle, "default",
        release=release,
        generated_at="2026-07-22T00:00:00+00:00",
        source_schema="simple.dbml",
        source_mapping="sharepoint-mapping.yaml",
    )
    assert "0.1.0-test" in md       # release tag
    assert "0.8" in md              # schema version
    assert "simple.dbml" in md
    assert "sharepoint-mapping.yaml" in md
    assert "2026-07-22T00:00:00+00:00" in md


def test_dictionary_powerquery_returns_report_ready_tables() -> None:
    """The dictionary ships as loadable queries so any report can surface it
    as a page: _DataDictionary (column rows) + _ModelInfo (metadata rows)."""
    schema, bundle = _simple()
    queries = generate_dictionary_powerquery(schema, bundle, "default")
    assert set(queries) == {
        "_DataDictionary.pq", "_ModelInfo.pq", "_UserAddedColumns.pq",
    }
    dd = queries["_DataDictionary.pq"]
    assert "#table(" in dd
    assert '"APP_Task", "DueDate", "Date"' in dd
    mi = queries["_ModelInfo.pq"]
    assert '"Generator", "dbml-sharepoint' in mi


def test_dictionary_powerquery_stamps_release_metadata() -> None:
    schema, bundle = _simple()
    release = load_release(FIXTURES / "release.yaml")
    mi = generate_dictionary_powerquery(
        schema, bundle, "default",
        release=release, generated_at="2026-07-22T00:00:00+00:00",
    )["_ModelInfo.pq"]
    assert "0.1.0-test" in mi
    assert "2026-07-22T00:00:00+00:00" in mi


def test_dictionary_powerquery_escapes_embedded_quotes() -> None:
    """Calculated formulas contain double quotes; M doubles them in string
    literals — an unescaped quote would break the whole query."""
    schema, bundle = _calculated()
    dd = generate_dictionary_powerquery(schema, bundle, "default")["_DataDictionary.pq"]
    assert '=IF([Severity]=""High"",10,1)' in dd


def test_dictionary_sql_views_from_values() -> None:
    schema, bundle = _simple()
    sql = generate_dictionary_sql(schema, bundle, "default")
    assert "[vw_APP_DataDictionary]" in sql
    assert "[vw_APP_ModelInfo]" in sql
    assert "FROM (VALUES" in sql
    assert "N'APP_Task'" in sql  # rows embedded, no landing table needed


def test_cli_report_writes_queries_and_docs(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from dbml_sharepoint.cli import app

    out = tmp_path / "reports"
    result = CliRunner().invoke(app, [
        "report",
        "--schema", str(FIXTURES / "simple.dbml"),
        "--mapping", str(FIXTURES / "sharepoint-mapping.yaml"),
        "--release", str(FIXTURES / "release.yaml"),
        "--site-role", "default",
        "--out", str(out),
    ])
    assert result.exit_code == 0, result.output
    assert (out / "powerquery" / "APP_Task.pq").exists()
    assert (out / "sql" / "views.sql").exists()
    assert (out / "guide.md").exists()
    dictionary = (out / "data-dictionary.md").read_text(encoding="utf-8")
    assert "0.1.0-test" in dictionary  # release metadata stamped
    # The dictionary is also emitted as report-loadable artefacts.
    model_info = (out / "powerquery" / "_ModelInfo.pq").read_text(encoding="utf-8")
    assert "0.1.0-test" in model_info
    assert (out / "powerquery" / "_DataDictionary.pq").exists()
    assert (out / "powerquery" / "_UserAddedColumns.pq").exists()
    views = (out / "sql" / "views.sql").read_text(encoding="utf-8")
    assert "[vw_APP_DataDictionary]" in views
    assert "[vw_APP_ModelInfo]" in views
    assert "[vw_APP_UserAddedColumns]" in views


def test_cli_report_works_without_release(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from dbml_sharepoint.cli import app

    out = tmp_path / "reports"
    result = CliRunner().invoke(app, [
        "report",
        "--schema", str(FIXTURES / "simple.dbml"),
        "--mapping", str(FIXTURES / "sharepoint-mapping.yaml"),
        "--site-role", "default",
        "--out", str(out),
    ])
    assert result.exit_code == 0, result.output
    assert (out / "data-dictionary.md").exists()


def test_cli_report_rejects_unknown_site_role(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from dbml_sharepoint.cli import app

    result = CliRunner().invoke(app, [
        "report",
        "--schema", str(FIXTURES / "simple.dbml"),
        "--mapping", str(FIXTURES / "sharepoint-mapping.yaml"),
        "--site-role", "no-such-role",
        "--out", str(tmp_path / "reports"),
    ])
    assert result.exit_code == 2
    assert "no-such-role" in result.output


# --- Reporting integration (display names, ordinals, HTML flags) ------------


def test_powerquery_renames_columns_to_display_titles() -> None:
    """The Power BI model must speak the same language as the forms and
    views staff see: with display names on, each query ends with a
    RenameColumns step from internal to display names (internal names stay
    the wire/OData contract; the rename is the last step)."""
    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    queries = generate_powerquery(schema, bundle, "default")
    project = queries["APP_Project.pq"]
    assert "RenamedForModel = Table.RenameColumns(" in project
    assert '{"SortOrder", "Sort Order"}' in project
    assert '{"ItemURL", "Item URL"}' in project
    assert "MissingField.Ignore" in project
    assert project.rstrip().endswith("RenamedForModel")


def test_powerquery_byte_stable_without_display_names() -> None:
    schema = parse_dbml(FIXTURES / "calculated.dbml")
    bundle = load_mapping(FIXTURES / "calculated-mapping.yaml")
    queries = generate_powerquery(schema, bundle, "default")
    assert all("RenameColumns" not in q for q in queries.values())


def test_dictionary_choice_members_carry_ordinals() -> None:
    """Choice values sort alphabetically in Power BI (Extreme before Low);
    the dictionary publishes declaration-order ordinals so report authors
    build sort-by-column mappings without hand-made lookup tables."""
    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    md = generate_data_dictionary(schema, bundle, "default")
    assert "Choice: 1. Open, 2. Closed" in md


def test_dictionary_flags_rich_text_as_html() -> None:
    schema = make_schema(
        make_table("Risk", column("Title", required=True), column("Detail", "richtext")),
    )
    bundle = make_bundle(entities=["Risk"])
    md = generate_data_dictionary(schema, bundle, "default")
    assert "HTML over OData" in md
    assert "strip markup" in md


# --- User-added column audit (reporting-layer drift detection) --------------


def test_user_added_columns_powerquery_audits_every_list() -> None:
    """_UserAddedColumns.pq reads each list's /fields collection live and
    filters IN M (never OData $filter): visible, not read-only, deletable
    (CanBeDeleted=false already covers sealed and base-type built-ins),
    then anti-joins the declared internal names. Empty on a healthy site."""
    schema, bundle = _simple()
    queries = generate_dictionary_powerquery(schema, bundle, "default")
    assert "_UserAddedColumns.pq" in queries
    q = queries["_UserAddedColumns.pq"]
    assert "/fields" in q
    assert "$select=InternalName,Title,TypeAsString,Hidden,ReadOnlyField,CanBeDeleted" in q
    assert "not [Hidden] and not [ReadOnlyField] and [CanBeDeleted]" in q
    assert "Table.Combine" in q
    for lst in ("APP_Project", "APP_Task", "APP_AppSettings"):
        assert f'Audit("{lst}"' in q
    # The single documented tenant exclusion.
    assert '"ComplianceAssetId"' in q


def test_user_added_columns_expected_sets_use_internal_names() -> None:
    """The anti-join set must hold declared INTERNAL field names — the
    lookup as 'Project', never the OData item path 'Project/Title' nor the
    derived join-key output 'ProjectId' (those exist only in the data
    queries' $select)."""
    schema, bundle = _simple()
    q = generate_dictionary_powerquery(schema, bundle, "default")["_UserAddedColumns.pq"]
    assert '"Project"' in q
    assert '"DueDate"' in q
    assert "Project/Title" not in q
    assert '"ProjectId"' not in q


def test_user_added_columns_sql_view_antijoins_information_schema() -> None:
    """vw_<prefix>UserAddedColumns lists landed columns the schema does not
    declare: INFORMATION_SCHEMA.COLUMNS over the landing tables, NOT EXISTS
    against embedded (list, expected column) VALUES — Id plus each landed
    name (lookups land as <name>Id). Empty by default; sees only what the
    extractor lands."""
    schema, bundle = _simple()
    sql = generate_dictionary_sql(schema, bundle, "default")
    assert "[vw_APP_UserAddedColumns]" in sql
    assert "INFORMATION_SCHEMA.COLUMNS" in sql
    assert "TABLE_SCHEMA = '$(LandingSchema)'" in sql
    assert "NOT EXISTS" in sql
    assert "(N'APP_Task', N'Id')" in sql
    assert "(N'APP_Task', N'ProjectId')" in sql
    assert "(N'APP_Task', N'DueDate')" in sql


def test_reporting_md_documents_user_added_column_audit() -> None:
    schema, bundle = _simple()
    md = generate_reporting_md(schema, bundle, "default")
    assert "## User-added column audit" in md
    assert "_UserAddedColumns" in md
    assert "vw_APP_UserAddedColumns" in md


def test_emit_reporting_writes_bundle_and_returns_relpaths(tmp_path: Path) -> None:
    """Both CLIs ship reporting through this one helper, so the artifact
    set cannot drift between them. It returns the exact relpaths written,
    POSIX separators, for checksums.txt."""
    from dbml_sharepoint.generators.reportgen import emit_reporting
    schema, bundle = _simple()
    release = load_release(FIXTURES / "release.yaml")

    relpaths = emit_reporting(
        tmp_path, schema, bundle, "default",
        release=release, generated_at="2026-05-04T00:00:00Z",
        source_schema="simple.dbml", source_mapping="sharepoint-mapping.yaml",
    )

    for fixed in ("reporting/sql/views.sql", "reporting/guide.md",
                  "reporting/data-dictionary.md"):
        assert fixed in relpaths
    assert any(p.startswith("reporting/powerquery/") and p.endswith(".pq")
               for p in relpaths)
    assert not any("\\" in p for p in relpaths)
    for relpath in relpaths:
        assert (tmp_path / relpath).is_file(), relpath
    # Nothing written outside reporting/, nothing written but not returned.
    on_disk = {p.relative_to(tmp_path).as_posix()
               for p in tmp_path.rglob("*") if p.is_file()}
    assert on_disk == set(relpaths)


def test_calculated_date_reports_as_date() -> None:
    """A calculated date column must land as a date in both reporting
    surfaces — M `type date` and SQL `DATE` — not the text fallback."""
    schema = make_schema(
        make_table(
            "Risk",
            column("Title", required=True),
            column("NextReviewDue", "calculated_date"),
        ),
    )
    bundle = make_bundle(
        entities=["Risk"],
        calculated_formulas={"Risk": {"NextReviewDue": "=DATE(2026,1,1)"}},
    )
    pq = generate_powerquery(schema, bundle, "default")["APP_Risk.pq"]
    assert "NextReviewDue" in pq
    assert "type date" in pq
    sql = generate_sql_views(schema, bundle, "default")
    assert any(
        "NextReviewDue" in line and " DATE" in line
        for line in sql.splitlines()
    ), sql


# --- Declared form behaviour in the reporting bundle -------------------------
#
# reportgen was not in the form_visibility branch's diff at all: bundles were
# byte-identical with and without every declaration. An analyst seeing a
# 100%-blank column could not tell it was hidden by design from a column
# that nobody fills in, and a save rule that governs the data was invisible
# to everyone who consumes the data.


def _declared() -> tuple[Schema, MappingBundle]:
    schema = make_schema(
        make_table(
            "Escalation",
            column("Title", required=True),
            column("Route"),
            column("Resolution"),
            column("Status"),
        ),
    )
    bundle = make_bundle(
        entities=["Escalation"],
        form_visibility={
            "Escalation": EntitySection(columns={
                # `Route: hidden` is the loader's shorthand for both flags off.
                "Route": FormVisibility(new=False, existing=False),
                "Resolution": FormVisibility(
                    new=False,
                    when=Group("all_of", (
                        Leaf(field="Status", op="eq", value="Resolved"),
                    )),
                ),
            }),
        },
        column_validation={
            "Escalation": EntitySection(columns={
                "Resolution": ColumnValidation(
                    when=Group("all_of", (
                        Leaf(field="Resolution", op="gt", value=10, measure="length"),
                    )),
                    message="Give at least a sentence.",
                ),
            }),
        },
    )
    return schema, bundle


def test_data_dictionary_reports_form_visibility_and_save_rules() -> None:
    schema, bundle = _declared()
    doc = generate_data_dictionary(schema, bundle, "default")
    assert "Populated when" in doc
    assert "Save rule" in doc
    # Described, never target syntax: `[$ID] != ''` means nothing to a
    # report author, and it is the one thing they must not have to decode.
    assert "[$ID]" not in doc
    assert "Never on a form" in doc                    # Route: hidden
    assert "Status eq 'Resolved'" in doc               # the when tree, described
    assert "Give at least a sentence." in doc          # the author's own message
    assert "length(Resolution) gt 10" in doc


def test_dictionary_powerquery_and_sql_carry_the_same_two_columns() -> None:
    """The analyst consuming the bundle sees what the form does, not just
    what the column is."""
    schema, bundle = _declared()
    pq = generate_dictionary_powerquery(schema, bundle, "default")["_DataDictionary.pq"]
    assert "PopulatedWhen = text" in pq
    assert "SaveRule = text" in pq
    assert "Give at least a sentence." in pq
    sql = generate_dictionary_sql(schema, bundle, "default")
    assert "PopulatedWhen" in sql
    assert "SaveRule" in sql


def test_user_added_columns_selects_the_deployed_formula_properties() -> None:
    """_UserAddedColumns is the only LIVE query in the bundle and already
    calls /fields on every refresh. Selecting the two formula properties
    turns it into a refresh-time check that the deployed contract still
    matches the dictionary — for free."""
    schema, bundle = _declared()
    pq = generate_dictionary_powerquery(schema, bundle, "default")["_UserAddedColumns.pq"]
    assert "ClientValidationFormula" in pq
    assert "ValidationFormula" in pq


def test_undeclared_columns_read_as_dashes_not_blanks() -> None:
    """Absence must be legible. An empty cell reads as missing data — the
    analyst cannot tell "no rule declared" from "the generator did not
    know", which is the same ambiguity this whole change exists to remove."""
    schema, bundle = _declared()
    doc = generate_data_dictionary(schema, bundle, "default")

    def cells(column: str) -> list[str]:
        row = next(ln for ln in doc.splitlines() if ln.startswith(f"| {column} |"))
        return [c.strip() for c in row.split("|")]

    # Columns 8 and 9 are Populated when / Save rule (6 and 7 are the
    # retirement pair, which this mapping declares for nothing).
    assert cells("Status")[8] == "—"
    assert cells("Status")[9] == "—"
    assert cells("Resolution")[8] != "—"
    assert cells("Resolution")[9] != "—"


def _retired() -> tuple[Schema, MappingBundle]:
    return (
        parse_dbml(FIXTURES / "retired.dbml"),
        load_mapping(FIXTURES / "retired-mapping.yaml"),
    )


def test_data_dictionary_documents_retirement() -> None:
    schema, bundle = _retired()
    md = generate_data_dictionary(schema, bundle, "default")
    assert "| Retired | Superseded by |" in md
    assert "| 2026-09-01 | SiteServicesStatus |" in md
    # A live column carries the em-dash placeholder, not a blank cell.
    assert "| SiteServicesStatus | Choice" in md


def test_dictionary_powerquery_and_sql_carry_retirement() -> None:
    schema, bundle = _retired()
    dd = generate_dictionary_powerquery(schema, bundle, "default")["_DataDictionary.pq"]
    assert "Retired = text, SupersededBy = text" in dd
    assert '"2026-09-01", "SiteServicesStatus"' in dd
    sql = generate_dictionary_sql(schema, bundle, "default")
    assert "[Retired]" in sql
    assert "[SupersededBy]" in sql
    assert "N'2026-09-01'" in sql


def test_user_added_columns_still_expects_retired_columns() -> None:
    """The whole point of retiring rather than deleting: the column stays
    declared, so the live drift audit must keep expecting it. A row for a
    retired column would erode the "any row here means investigate"
    contract on every refresh, forever."""
    schema, bundle = _retired()
    q = generate_dictionary_powerquery(schema, bundle, "default")["_UserAddedColumns.pq"]
    assert '"OperationsStatus"' in q
    sql = generate_dictionary_sql(schema, bundle, "default")
    assert "N'OperationsStatus'" in sql


def test_powerquery_still_selects_retired_columns() -> None:
    """History is the entire point; the list query must keep selecting the
    retired column."""
    schema, bundle = _retired()
    q = generate_powerquery(schema, bundle, "default")["APP_Board.pq"]
    assert "OperationsStatus" in q


def _kind_swapped(
    monkeypatch: pytest.MonkeyPatch, column_name: str, kind: str,
) -> None:
    """Make `_build_plans` see one column as a field kind it does not handle.

    Monkeypatched rather than schema-driven on purpose: the guard has to hold
    for the NEXT kind somebody adds to `typemap.FieldKind`, and a kind that
    exists is a kind somebody has already had the chance to wire up here.
    """
    def fake(col: Column, enum_names: set[str]) -> SPField:
        sp = map_column(col, enum_names)
        if col.name == column_name:
            return replace(sp, kind=cast("FieldKind", kind))
        return sp

    monkeypatch.setattr(reportgen, "map_column", fake)


def test_build_plans_refuses_a_field_kind_it_does_not_handle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unhandled `sp.kind` must abort, because the two drift audits
    disagree about it and neither of them can say so.

    `field_internal_names` is appended BEFORE the match, so an unhandled kind
    is recorded as a column the list is expected to have while contributing no
    `$select`, no Power Query type and no SQL column. `_UserAddedColumns.pq`
    is built from the expected list, so the M audit sees nothing wrong; the
    SQL audit is built from `sql_columns`, so it reports the same column as an
    unexpected user-added one. Two audits over one deployment, contradicting
    each other, with the column silently absent from every query that was
    supposed to carry it.

    A `case _` that raises is the only version of this the build can see.
    """
    schema, bundle = _simple()
    _kind_swapped(monkeypatch, "Title", "Uncharted")

    with pytest.raises(ValueError, match="Uncharted") as err:
        generate_powerquery(schema, bundle, "default")

    # Named well enough to fix from the message alone: which column, on which
    # entity, and what has to be taught about it.
    assert "Title" in str(err.value)
    assert "Project" in str(err.value)


def test_the_sql_view_builder_refuses_the_same_unhandled_kind(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The SQL side is the audit that reports a FALSE POSITIVE on an
    unhandled kind, so it must fail closed too rather than emitting a view
    that quietly omits the column."""
    schema, bundle = _simple()
    _kind_swapped(monkeypatch, "Title", "Uncharted")

    with pytest.raises(ValueError, match="Uncharted"):
        generate_sql_views(schema, bundle, "default")


def test_the_dictionary_refuses_a_field_kind_it_has_no_arm_for(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`generate_data_dictionary` is the ONE entry point that never calls
    `_build_plans`, so the guard there cannot cover it.

    `_sp_type_cell` ended `return sp.kind`, which put the raw internal token
    -- `MultiChoice` -- in the "SharePoint type" column of
    data-dictionary.md, `_DataDictionary.pq` and `vw_<prefix>DataDictionary`
    alike. That is a document stating a column's type wrongly in the one
    place a report author goes to look it up, and nothing else in this module
    can see it happen.

    The loadable dictionary tables were already covered, incidentally:
    `generate_dictionary_powerquery` and `generate_dictionary_sql` both build
    `_UserAddedColumns` and so go through `_build_plans` before they return.
    The markdown page is the only entry point in this module that does not,
    which is exactly why the leak survived there.
    """
    schema, bundle = _simple()
    _kind_swapped(monkeypatch, "Title", "Uncharted")

    with pytest.raises(ValueError, match="Uncharted") as err:
        generate_data_dictionary(schema, bundle, "default")

    assert "_sp_type_cell" in str(err.value)


# --- Multi-value columns ----------------------------------------------------


def _multi_value(*, display_names: bool = False) -> tuple[Schema, MappingBundle]:
    """A schema declaring a multi-value column — the thing S9 exists to report.

    `AuditEvents` rather than `Events` so the display-name test has a name that
    auto-splits, and one member carries a space because that is what rules the
    separator choice: a multi-value member is a phrase, not a token.
    """
    schema = make_schema(
        make_table(
            "Platform",
            column("Title", required=True),
            column("AuditEvents", "audit_event[]"),
        ),
        enums=[make_enum("audit_event", "View", "Edit", "Permission change")],
    )
    if display_names:
        return schema, make_bundle(entities=["Platform"], display_name_mode="auto")
    return schema, make_bundle(entities=["Platform"])


def test_powerquery_joins_a_multi_value_column_into_one_text_cell() -> None:
    """MEASURED 2026-08-10: under `odata=nometadata`, which is what the
    Power Query layer speaks, a multi-value item value comes back as a bare
    JSON array — so the cell holds a LIST, not text.

    The scalar arm's `Table.TransformColumnTypes(…, type text)` over a list
    does not produce a mistyped column; it produces an Error value in every
    populated cell, and the query still loads. The join has to happen before
    anything tries to type it, and the type is then ascribed by the step that
    produced the text.
    """
    schema, bundle = _multi_value()
    q = generate_powerquery(schema, bundle, "default")["APP_Platform.pq"]

    assert "$select=Id,Title,AuditEvents" in q
    assert "Table.TransformColumns(" in q
    assert 'Text.Combine(_, "; ")' in q
    assert "type text}" in q
    # The raw list must never reach the typing step: that is the failure this
    # arm exists to avoid, not a cosmetic difference.
    assert '{"AuditEvents", type text},' not in q
    assert '{"AuditEvents", type text}\n' not in q


def test_powerquery_renders_an_empty_multi_value_set_as_blank() -> None:
    """MEASURED 2026-08-10: an empty multi-value set reads back as `null`,
    NOT as `[]`.

    `Text.Combine(null, "; ")` raises, and a raise inside a transform fails
    the whole refresh — one row that has never had a value would take the
    report down. Guarded, the cell is blank, which is what "no members" means.
    """
    schema, bundle = _multi_value()
    q = generate_powerquery(schema, bundle, "default")["APP_Platform.pq"]

    assert "each if _ = null or List.IsEmpty(_) then null" in q


def test_sql_view_gives_a_multi_value_column_nvarchar_max() -> None:
    """A joined set has no meaningful 255 bound, and SQL Server truncates a
    CAST to NVARCHAR(255) silently."""
    schema, bundle = _multi_value()
    sql = generate_sql_views(schema, bundle, "default")

    assert "CAST(t.[AuditEvents] AS NVARCHAR(MAX)) AS [AuditEvents]" in sql


def test_both_drift_audits_agree_about_a_multi_value_column() -> None:
    """The audits are built from two different lists — the M one from
    `field_internal_names`, the SQL one from `sql_columns` — and a kind that
    lands in one but not the other makes them contradict each other over the
    same deployment. A multi-value column must be expected by both."""
    schema, bundle = _multi_value()

    m_audit = generate_dictionary_powerquery(
        schema, bundle, "default",
    )["_UserAddedColumns.pq"]
    sql_audit = generate_dictionary_sql(schema, bundle, "default")

    assert '"AuditEvents"' in m_audit
    assert "(N'APP_Platform', N'AuditEvents')" in sql_audit


def test_dictionary_describes_a_multi_value_column_in_human_words() -> None:
    """`MultiChoice` is this codebase's internal token for FieldTypeKind 15.
    The dictionary is read by report authors, so it says what the column is
    and how the export spells a set."""
    schema, bundle = _multi_value()
    md = generate_data_dictionary(schema, bundle, "default")

    assert "Choice (multiple): 1. View, 2. Edit, 3. Permission change" in md
    assert '"; "' in md
    assert "MultiChoice" not in md


def test_display_names_still_reach_a_multi_value_column() -> None:
    """The joined column is not in `m_types`, which is where every other
    renameable output name comes from — so without an explicit entry the one
    column type this stage added would be the one that never got its display
    title, and only a reader comparing two report pages would ever notice."""
    schema, bundle = _multi_value(display_names=True)
    q = generate_powerquery(schema, bundle, "default")["APP_Platform.pq"]

    assert '{"AuditEvents", "Audit Events"}' in q
