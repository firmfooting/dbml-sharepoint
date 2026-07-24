# test/test_reportgen.py
from pathlib import Path

from dbml_sharepoint.mapping_loader import MappingBundle, load_mapping
from dbml_sharepoint.parser import Schema, parse_dbml
from dbml_sharepoint.release import load_release
from dbml_sharepoint.reportgen import (
    generate_data_dictionary,
    generate_dictionary_powerquery,
    generate_dictionary_sql,
    generate_powerquery,
    generate_reporting_md,
    generate_sql_views,
)

FIXTURES = Path(__file__).parent / "fixtures"


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
    schema, bundle = _simple()
    md = generate_reporting_md(schema, bundle, "default")
    assert "| APP_Task | ProjectId | APP_Project | Id |" in md
    assert "SiteUrl" in md  # parameter setup instructions


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
    assert (out / "REPORTING.md").exists()
    dictionary = (out / "DATA-DICTIONARY.md").read_text(encoding="utf-8")
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
    assert (out / "DATA-DICTIONARY.md").exists()


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


def test_dictionary_flags_rich_text_as_html(tmp_path: Path) -> None:
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Risk {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar [not null]\n"
        "  Detail richtext\n"
        "}\n",
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
    from dbml_sharepoint.reportgen import emit_reporting
    schema, bundle = _simple()
    release = load_release(FIXTURES / "release.yaml")

    relpaths = emit_reporting(
        tmp_path, schema, bundle, "default",
        release=release, generated_at="2026-05-04T00:00:00Z",
        source_schema="simple.dbml", source_mapping="sharepoint-mapping.yaml",
    )

    for fixed in ("reporting/sql/views.sql", "reporting/REPORTING.md",
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


def test_calculated_date_reports_as_date(tmp_path: Path) -> None:
    """A calculated date column must land as a date in both reporting
    surfaces — M `type date` and SQL `DATE` — not the text fallback."""
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
        "    NextReviewDue: '=DATE(2026,1,1)'\n",
        encoding="utf-8",
    )
    schema = parse_dbml(tmp_path / "s.dbml")
    bundle = load_mapping(tmp_path / "m.yaml")
    pq = generate_powerquery(schema, bundle, "default")["APP_Risk.pq"]
    assert "NextReviewDue" in pq
    assert "type date" in pq
    sql = generate_sql_views(schema, bundle, "default")
    assert any(
        "NextReviewDue" in line and " DATE" in line
        for line in sql.splitlines()
    ), sql
