"""Validator: column formatting."""
from pathlib import Path

from _paths import FIXTURES
from _validator_helpers import (
    _bundle_with_formulas,
    _schema,
    _view_errors,
    _view_inputs,
)

from dbml_sharepoint.analysis.validator import (
    validate,
    validate_against_mapping,
)
from dbml_sharepoint.model.mapping_loader import (
    load_mapping,
)
from dbml_sharepoint.model.parser import (
    Column,
    Reference,
    Table,
    parse_dbml,
)

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
