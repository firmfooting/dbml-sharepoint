"""Validator: column formatting."""
from pathlib import Path

from _findings import by_severity, messages, none_of, only
from _model import bundle as make_bundle
from _model import column as make_column
from _model import person as make_person
from _model import ref as make_ref
from _model import schema as make_schema
from _model import table as make_table
from _packs import blocks, entities, pack
from _paths import FIXTURES
from _validator_helpers import _project_errors, _project_inputs

from dbml_sharepoint.analysis.findings import FindingCode, Location, Section
from dbml_sharepoint.analysis.validator import (
    validate,
    validate_against_mapping,
)
from dbml_sharepoint.model.conditions import Condition, parse_condition
from dbml_sharepoint.model.mapping_loader import load_mapping
from dbml_sharepoint.model.mapping_types import FormFormatting, ListValidation, ViewDef
from dbml_sharepoint.model.parser import (
    Column,
    Table,
    parse_dbml,
)

# --- Column formatting ------------------------------------------------------


def test_formatter_field_refs_walks_nested_structures() -> None:
    from dbml_sharepoint.analysis.column_refs import formatter_field_refs

    refs = formatter_field_refs({
        "elmType": "div",
        "style": {"color": "=if([$Status] == 'Open', 'green', [$RiskScore])"},
        "children": [{"txtContent": "[$DueDate]"}, {"txtContent": "plain"}],
    })
    assert refs == frozenset({"Status", "RiskScore", "DueDate"})

def test_column_formatting_validation() -> None:
    errors = _project_errors(column_formatting={
        "Widget": {"Anything": {"elmType": "div"}},
        "Project": {
            "Nope": {"elmType": "div"},
            "Status": {"txtContent": "x"},
            "SortOrder": {"elmType": "div", "txtContent": "[$Missing]"},
        },
    })
    assert only(errors, FindingCode.UNKNOWN_ENTITY).location == Location(
        Section.COLUMN_FORMATTING, entity="Widget",
    )
    assert only(errors, FindingCode.FORMATTER_COLUMN_NOT_RENDERED).location == Location(
        Section.COLUMN_FORMATTING, entity="Project", column="Nope",
    )
    # Status declares no elmType.
    assert only(errors, FindingCode.FORMATTER_MISSING_ELMTYPE).location == Location(
        Section.COLUMN_FORMATTING, entity="Project", column="Status",
    )
    bad_ref = only(errors, FindingCode.FORMATTER_FIELD_NOT_RENDERED)
    assert bad_ref.location == Location(
        Section.COLUMN_FORMATTING, entity="Project", column="SortOrder",
    )
    assert "Missing" in bad_ref.message
    ok = _project_errors(column_formatting={
        "Project": {"Status": {"elmType": "div", "txtContent": "[$SortOrder]"}},
    })
    assert ok == []

def test_misspelled_column_under_a_pill_style_reports_only_the_misspelling(
    tmp_path: Path,
) -> None:
    """A `pill` has no calculated form, so `calculated_type_for_style` is
    None for it, and a column absent from the DBML has type None too. The
    two used to compare equal and raise STYLE_REQUIRES_CALCULATED reading
    "pill on None requires calculated: true", naming a type that does not
    exist and prescribing a key `_pill` refuses at load time.

    The positive half is asserted with the negative: without it this passes
    if the style-spec loop stops running altogether.
    """
    schema, bundle = pack(
        tmp_path,
        dbml="""
            Table Risk {
              Id int [pk, increment]
              Title nvarchar [not null]
              Owner nvarchar
            }
        """,
        mapping=blocks(entities("Risk"), """
            column_formatting:
              Risk:
                Ownr: { style: pill, map: { Open: good } }
        """),
    )
    findings = validate_against_mapping(schema, bundle)
    misspelled = only(findings, FindingCode.FORMATTER_COLUMN_NOT_RENDERED)
    assert misspelled.location == Location(
        Section.COLUMN_FORMATTING, entity="Risk", column="Ownr",
    )
    none_of(findings, FindingCode.STYLE_REQUIRES_CALCULATED)
    none_of(findings, FindingCode.STYLE_CALCULATED_TYPE_MISMATCH)

def test_severity_on_a_calculated_text_column_still_requires_decoding(
    tmp_path: Path,
) -> None:
    """The other side of the guard above: the rule must still fire where it
    should, or the repair has disabled it and the suite cannot tell."""
    schema, bundle = pack(
        tmp_path,
        dbml="""
            Table Risk {
              Id int [pk, increment]
              Title nvarchar [not null]
              Band calculated_text
            }
        """,
        mapping=blocks(entities("Risk"), """
            calculated_formulas:
              Risk:
                Band: "=IF([Title]='','Low','High')"
            column_formatting:
              Risk:
                Band: { style: severity, map: { Low: good, High: severe } }
        """),
    )
    finding = only(
        validate_against_mapping(schema, bundle),
        FindingCode.STYLE_REQUIRES_CALCULATED,
    )
    assert finding.severity == "error"
    assert finding.location == Location(
        Section.COLUMN_FORMATTING, entity="Risk", column="Band",
    )
    assert "calculated: true" in finding.message

def test_view_formatting_field_refs_validated() -> None:
    errors = _project_errors(views={"Project": [ViewDef(
        title="V",
        fields=["Title"],
        formatting={"additionalRowClass": "=if([$Ghost] == 1, 'x', '')"},
    )]})
    f = only(errors, FindingCode.FORMATTER_FIELD_NOT_RENDERED)
    assert f.location == Location(Section.VIEWS, entity="Project", view="V")
    assert "Ghost" in f.message

def test_form_formatting_validation() -> None:
    errors = _project_errors(form_formatting={
        "Widget": FormFormatting(header={"elmType": "div"}),
        "Project": FormFormatting(
            header={"elmType": "div", "txtContent": "[$Ghost]"},
            body={"sections": [{"displayname": "X", "fields": ["Title", "Nope"]}]},
        ),
    })
    assert only(errors, FindingCode.UNKNOWN_ENTITY).location == Location(
        Section.FORM_FORMATTING, entity="Widget",
    )
    ghost = only(errors, FindingCode.FORMATTER_FIELD_NOT_RENDERED)
    assert ghost.location == Location(
        Section.FORM_FORMATTING, entity="Project", sub="header",
    )
    assert "Ghost" in ghost.message
    section_field = only(errors, FindingCode.FORM_SECTION_FIELD_NOT_RENDERED)
    assert "Nope" in section_field.message
    ok = _project_errors(form_formatting={
        "Project": FormFormatting(
            body={"sections": [{"displayname": "X", "fields": ["Title", "Status"]}]},
        ),
    })
    assert ok == []

def _when(*leaves: dict[str, object]) -> Condition:
    """A condition tree, through the real parser rather than by hand.

    `parse_condition` is a pure structural parse of what YAML already
    produced -- no file, no loader -- so calling it here is the same tree the
    mapping would have carried. Spelling `Group("all_of", (Leaf(...),))` out
    instead would be a test asserting its own idea of how a bare list nests.
    """
    return parse_condition(list(leaves), "when")

def test_list_validation_rules_validated() -> None:
    schema, bundle = _project_inputs(list_validation={
        "Widget": ListValidation(
            when=_when({"field": "Title", "op": "is_not_null"}), message="x",
        ),
        "Project": ListValidation(
            when=_when({"field": "Ghost", "op": "eq", "value": "x"}), message="x",
        ),
    })
    errors = by_severity(validate_against_mapping(schema, bundle), "error")
    assert only(errors, FindingCode.UNKNOWN_ENTITY).location == Location(
        Section.LIST_VALIDATION, entity="Widget",
    )
    assert "Ghost" in only(errors, FindingCode.INVALID_CONDITION).message

def test_list_validation_rejects_unsupported_column_types() -> None:
    """SP list validation formulas cannot reference calculated, person,
    lookup or multi-line columns. Reject at build, not at paste."""
    schema = make_schema(make_table(
        "Risk",
        make_column("Title", required=True),
        make_column("Score", "calculated_number"),
        make_person("Owner"),
    ))
    bundle = make_bundle(
        entities=["Risk"],
        calculated_formulas={"Risk": {"Score": "=1"}},
        list_validation={"Risk": ListValidation(
            when=_when(
                {"field": "Score", "op": "gt", "value": 0},
                {"field": "Owner", "op": "is_not_null"},
            ),
            message="x",
        )},
    )
    errors = by_severity(validate_against_mapping(schema, bundle), "error")
    # The condition grammar hands its rejections back as prose under one
    # code, so the type it refused lives only in the message.
    reasons = messages(errors, FindingCode.INVALID_CONDITION)
    assert any("Score" in m and "calculated" in m.lower() for m in reasons), reasons
    assert any("Owner" in m and "person" in m.lower() for m in reasons), reasons

def test_today_offset_valid_on_calculated_date() -> None:
    """A calculated_date column stores DateTime values, so 'today' offset
    view filters must accept it (the NextReviewDue 'Reviews due' case).

    This test used to assert that no message contained "offsets apply only".
    That sentence is written NOWHERE in `src`, so the assertion could not
    fail and the test passed while checking nothing. The claim it meant to
    make is simply that the filter is accepted: no error at all.
    """
    schema = make_schema(make_table(
        "Risk",
        make_column("Title", required=True),
        make_column("NextReviewDue", "calculated_date"),
        # The table needs a note or ENTITY_HAS_NO_NOTE joins the error list
        # this test asserts is empty.
        note="The fixture risk list.",
    ))
    bundle = make_bundle(
        entities=["Risk"],
        calculated_formulas={"Risk": {"NextReviewDue": "=DATE(2026,1,1)"}},
        views={"Risk": [ViewDef(
            title="Due",
            fields=["Title", "NextReviewDue"],
            where=_when({"field": "NextReviewDue", "op": "leq", "value": "today+30"}),
        )]},
    )
    findings = validate_against_mapping(schema, bundle)
    assert not by_severity(findings, "error"), findings

def test_watched_list_column_must_exist() -> None:
    """watched_lists is validated nowhere: a misspelled column simply
    never fires the status capture it was declared for."""
    from dbml_sharepoint.model.mapping_types import WatchedList

    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    bundle.mapping.watched_lists = [WatchedList(entity="Task", column="NoSuchColumn")]
    findings = validate_against_mapping(schema, bundle)
    f = only(findings, FindingCode.WATCHED_COLUMN_NOT_RENDERED)
    assert f.severity == "error"
    assert f.location == Location(Section.WATCHED_LISTS)
    assert "NoSuchColumn" in f.message

def test_polymorphic_pattern_columns_must_exist() -> None:
    """The manifest surfaces these so downstream flows validate the logical
    FK. A misspelled field or discriminator publishes a contract against a
    column that does not exist."""
    from dbml_sharepoint.model.mapping_types import PolymorphicPattern

    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    bundle.mapping.polymorphic_patterns = [
        PolymorphicPattern(list="Task", field="NoSuchField", discriminator="NoSuchType"),
    ]
    findings = validate_against_mapping(schema, bundle)
    named = messages(findings, FindingCode.POLYMORPHIC_COLUMN_NOT_RENDERED)
    # Both roles are reported, and by name. The field and the discriminator
    # are two different mistakes an author can make independently.
    assert any("NoSuchField" in m for m in named), named
    assert any("NoSuchType" in m for m in named), named

def test_watched_list_entity_must_exist() -> None:
    from dbml_sharepoint.model.mapping_types import WatchedList

    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    bundle.mapping.watched_lists = [WatchedList(entity="Tsak", column="Status")]
    findings = validate_against_mapping(schema, bundle)
    f = only(findings, FindingCode.UNKNOWN_ENTITY)
    assert f.severity == "error"
    assert f.location == Location(Section.WATCHED_LISTS)
    assert "Tsak" in f.message

def test_polymorphic_pattern_entity_must_exist() -> None:
    from dbml_sharepoint.model.mapping_types import PolymorphicPattern

    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    bundle.mapping.polymorphic_patterns = [
        PolymorphicPattern(list="Tsak", field="Status", discriminator="Status"),
    ]
    findings = validate_against_mapping(schema, bundle)
    f = only(findings, FindingCode.UNKNOWN_ENTITY)
    assert f.severity == "error"
    assert f.location == Location(Section.POLYMORPHIC_PATTERNS)
    assert "Tsak" in f.message

def test_versioning_override_entity_must_exist() -> None:
    """A misspelled entity under `versioning.overrides` leaves the real
    list on the defaults (versioning ON when the author turned it off),
    and nothing reads the orphan block, so nothing reported it."""
    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    bundle.mapping.versioning_overrides["Tsak"] = {"enable_versioning": False}
    findings = validate_against_mapping(schema, bundle)
    f = only(findings, FindingCode.UNKNOWN_ENTITY)
    assert f.severity == "error"
    assert f.location == Location(Section.VERSIONING, sub="overrides")
    assert "Tsak" in f.message

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
    findings = validate(make_schema(table))
    f = only(findings, FindingCode.AUTO_INCREMENT_PK_MUST_BE_ID)
    assert f.severity == "error"
    assert "TicketId" in f.message

def test_auto_increment_column_named_id_is_accepted() -> None:
    schema = make_schema(make_table("Ticket", make_column("Title", required=True)))
    assert by_severity(validate(schema), "error") == []

def test_column_named_id_that_is_not_the_identity_is_rejected() -> None:
    """The inverse: SharePoint reserves ID on every list, so a plain
    `Id nvarchar` was emitted as a Text field against a name that already
    exists. RESERVED_NAMES omitted it."""
    table = Table(name="Ticket", columns=[
        Column(name="Id", type="nvarchar"),
        Column(name="Title", type="nvarchar", required=True),
    ])
    findings = validate(make_schema(table))
    f = only(findings, FindingCode.RESERVED_COLUMN_NAME)
    assert f.severity == "error"
    assert "Id" in f.message

def test_calculated_formula_referencing_id_is_rejected() -> None:
    """The reference check compared against the raw DBML column set rather
    than the RENDERED one. `Id int [pk, increment]` is skipped at render
    time (typemap returns Skip and jsgen continues), so a formula naming
    [Id] passed validation and was posted against a column the deploy never
    creates. SharePoint answers HTTP 500 mid-paste, which is exactly what
    this check's own comment says it exists to prevent."""
    schema = make_schema(make_table(
        "Risk", make_column("Title", required=True), make_column("Ref", "calculated_text"),
    ))
    bundle = make_bundle(
        entities=["Risk"],
        calculated_formulas={"Risk": {"Ref": '=CONCATENATE("R-",[Id])'}},
    )
    findings = validate_against_mapping(schema, bundle)
    f = only(findings, FindingCode.CALCULATED_FORMULA_UNKNOWN_COLUMN)
    assert f.severity == "error"
    assert "[Id]" in f.message

def test_calculated_formula_referencing_a_phase_two_lookup_is_rejected() -> None:
    """jsgen orders calculated fields only within fields_phase1 and ignores
    phase2_lookups, so a formula naming a DEFERRED lookup was emitted in
    Phase 1, before the column it references exists. A self-referencing
    lookup is always deferred, so this is reachable from any hierarchy."""
    schema = make_schema(make_table(
        "Risk",
        make_column("Title", required=True),
        make_ref("Parent", "Risk.Id"),
        make_column("Label", "calculated_text"),
    ))
    bundle = make_bundle(
        entities=["Risk"],
        calculated_formulas={"Risk": {"Label": "=CONCATENATE([Title],[Parent])"}},
    )
    findings = validate_against_mapping(schema, bundle)
    f = only(findings, FindingCode.CALCULATED_FORMULA_DEFERRED_LOOKUP)
    assert f.severity == "error"
    # This finding carries no location, so both the offending formula and the
    # column it names have to reach the reader through the message.
    assert "Risk.Label" in f.message and "[Parent]" in f.message

def test_calculated_formula_referencing_a_phase_one_column_is_fine() -> None:
    schema = make_schema(make_table(
        "Risk", make_column("Title", required=True), make_column("Label", "calculated_text"),
        note="The fixture risk list.",
    ))
    bundle = make_bundle(
        entities=["Risk"], calculated_formulas={"Risk": {"Label": "=CONCATENATE([Title])"}},
    )
    assert by_severity(validate_against_mapping(schema, bundle), "error") == []
