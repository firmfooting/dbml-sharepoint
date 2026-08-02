"""Validator: calculated columns, and a lookup target's display column."""
from pathlib import Path

import pytest
from _builders import ID_PK, table
from _findings import by_severity, none_of, only
from _packs import blocks, entities, entity, pack
from _paths import FIXTURES
from _validator_helpers import _bundle_with_formulas, _schema

from dbml_sharepoint.analysis.findings import FindingCode, Location, Section
from dbml_sharepoint.analysis.validator import (
    validate,
    validate_against_mapping,
)
from dbml_sharepoint.model.mapping_loader import (
    CrossSiteRef,
    MappingBundle,
    load_mapping,
)
from dbml_sharepoint.model.parser import (
    Column,
    Reference,
    Schema,
    Table,
    TableIndex,
    parse_dbml,
)

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
    none_of(validate(_schema(table)), FindingCode.UNKNOWN_COLUMN_TYPE)

def test_valid_calculated_fixture_has_no_errors() -> None:
    schema, bundle = _calc_inputs()
    findings = validate(schema) + validate_against_mapping(schema, bundle)
    assert not by_severity(findings, "error")

def test_calculated_column_without_formula_is_error() -> None:
    schema, bundle = _calc_inputs()
    del bundle.mapping.calculated_formulas["Risk"]["RiskScore"]
    findings = validate_against_mapping(schema, bundle)
    f = only(findings, FindingCode.CALCULATED_COLUMN_HAS_NO_FORMULA)
    assert f.severity == "error"
    # No location on this one, so the column has to reach the reader in prose.
    assert "Risk.RiskScore" in f.message

def test_orphan_calculated_formula_is_error() -> None:
    schema, bundle = _calc_inputs()
    bundle.mapping.calculated_formulas["Risk"]["NotAColumn"] = "=1"
    findings = validate_against_mapping(schema, bundle)
    f = only(findings, FindingCode.FORMULA_TARGET_NOT_CALCULATED)
    assert f.severity == "error"
    assert f.location == Location(Section.CALCULATED_FORMULAS, entity="Risk")
    assert "NotAColumn" in f.message

def test_calculated_formula_must_start_with_equals() -> None:
    schema, bundle = _calc_inputs()
    bundle.mapping.calculated_formulas["Risk"]["RiskScore"] = 'IF([Severity]="High",10,1)'
    f = only(
        validate_against_mapping(schema, bundle),
        FindingCode.CALCULATED_FORMULA_MISSING_EQUALS,
    )
    assert f.severity == "error"
    assert "Risk.RiskScore" in f.message

def test_calculated_formula_over_sp_limit_is_error() -> None:
    schema, bundle = _calc_inputs()
    bundle.mapping.calculated_formulas["Risk"]["RiskScore"] = "=" + "1+" * 600 + "1"
    f = only(
        validate_against_mapping(schema, bundle),
        FindingCode.CALCULATED_FORMULA_TOO_LONG,
    )
    assert f.severity == "error"
    # The limit the author has to get under.
    assert "1024" in f.message

def test_calculated_formula_unknown_column_reference_is_error() -> None:
    """SharePoint validates a formula's [Column] references when the field is
    created, so a reference that resolves to nothing fails the deployment with
    HTTP 500 ("The formula refers to a column that does not exist"). The build
    must fail closed instead of shipping the manifest with 0 findings."""
    schema, bundle = _calc_inputs()
    bundle.mapping.calculated_formulas["Risk"]["RiskScore"] = (
        '=IF([Severty]="High",10,1)'  # misspelled Severity
    )
    f = only(
        validate_against_mapping(schema, bundle),
        FindingCode.CALCULATED_FORMULA_UNKNOWN_COLUMN,
    )
    assert f.severity == "error"
    assert "[Severty]" in f.message
    # Bracket text inside string literals is NOT a column reference.
    bundle.mapping.calculated_formulas["Risk"]["RiskScore"] = (
        '=IF([Severity]="[Not A Column]",10,1)'
    )
    none_of(
        validate_against_mapping(schema, bundle),
        FindingCode.CALCULATED_FORMULA_UNKNOWN_COLUMN,
    )

def test_calculated_formula_self_reference_is_error() -> None:
    schema, bundle = _calc_inputs()
    bundle.mapping.calculated_formulas["Risk"]["RiskScore"] = "=[RiskScore]+1"
    f = only(
        validate_against_mapping(schema, bundle),
        FindingCode.CALCULATED_FORMULA_SELF_REFERENCE,
    )
    assert f.severity == "error"
    assert "Risk.RiskScore" in f.message

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
    f = only(
        validate_against_mapping(_schema(parent, child), bundle),
        FindingCode.CALCULATED_FORMULA_UNSUPPORTED_OPERAND,
    )
    assert f.severity == "error"
    # One code covers every refused operand type, so WHICH type it was, and
    # which types are allowed instead, live only in the message.
    assert "Action.RiskCopy" in f.message and "[Risk]" in f.message
    assert "Lookup" in f.message
    # Naming the supported set matters more than naming the excluded one: an
    # author who reads "not a Lookup" still has to guess what IS allowed.
    assert "Yes/No" in f.message

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
    f = only(
        validate_against_mapping(_schema(table), bundle),
        FindingCode.CALCULATED_FORMULA_UNSUPPORTED_OPERAND,
    )
    assert f.severity == "error"
    assert "Risk.OwnerCopy" in f.message and "[Owner]" in f.message
    assert "Person" in f.message
    assert "Yes/No" in f.message

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
    f = only(
        validate_against_mapping(_schema(table), bundle),
        FindingCode.CALCULATED_FORMULA_UNSUPPORTED_OPERAND,
    )
    assert f.severity == "error"
    assert "Risk.Copy" in f.message and "[Source]" in f.message
    # The probed description is the whole point of the parametrisation.
    assert described_as in f.message

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
    none_of(
        validate_against_mapping(_schema(table), bundle),
        FindingCode.CALCULATED_FORMULA_UNSUPPORTED_OPERAND,
    )

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
    none_of(
        validate_against_mapping(_schema(unit, project), bundle),
        FindingCode.CALCULATED_FORMULA_UNKNOWN_COLUMN,
    )

def test_calculated_formula_circular_references_are_error() -> None:
    schema, bundle = _calc_inputs()
    bundle.mapping.calculated_formulas["Risk"]["RiskScore"] = '=IF([RiskBand]="Red",10,1)'
    bundle.mapping.calculated_formulas["Risk"]["RiskBand"] = '=IF([RiskScore]>5,"Red","Green")'
    f = only(validate_against_mapping(schema, bundle), FindingCode.CALCULATED_FORMULA_CYCLE)
    assert f.severity == "error"
    assert f.location == Location(Section.CALCULATED_FORMULAS, entity="Risk")
    # Both members of the cycle, or the author cannot see what to break.
    assert "RiskBand" in f.message and "RiskScore" in f.message

def test_indexed_calculated_column_is_error() -> None:
    schema, bundle = _calc_inputs()
    next(table for table in schema.tables if table.name == "Risk").indexes.append(
        TableIndex(("RiskScore",)),
    )
    f = only(validate_against_mapping(schema, bundle), FindingCode.INDEX_ON_CALCULATED_COLUMN)
    assert f.severity == "error"
    assert "'RiskScore'" in f.message

# --- Lookup target's display column must be indexable -----------------------


def _calculated_display_inputs(
    tmp_path: Path, *, accepted: bool,
) -> tuple[Schema, MappingBundle]:
    event = (
        entity("Event", display_column="Label", accept_unindexable_display_column="true")
        if accepted
        else entity("Event", display_column="Label")
    )
    return pack(
        tmp_path,
        dbml=blocks(
            table("Event", ID_PK, "Ref nvarchar", "Label calculated_text"),
            table("FollowUp", ID_PK, "Event int [ref: > Event.Id]"),
        ),
        mapping=entities(event, "FollowUp"),
    )

def test_a_calculated_display_column_warns_about_the_form(tmp_path: Path) -> None:
    """A warning, not an error: a target that stays under 5,000 has no problem.
    But the message must say the FORM breaks — "cannot be indexed" does not tell
    an author what their users will see."""
    schema, bundle = _calculated_display_inputs(tmp_path, accepted=False)
    f = only(
        validate_against_mapping(schema, bundle),
        FindingCode.CALCULATED_DISPLAY_COLUMN_UNINDEXABLE,
    )
    # Not an error: a small list is a legitimate case.
    assert f.severity == "warning"
    assert "Label" in f.message
    # "cannot be indexed" does not tell an author what their users will see.
    assert "new-item form" in f.message
    assert "accept_unindexable_display_column" in f.message

def test_accepting_it_silences_the_warning_completely(tmp_path: Path) -> None:
    """Silent, not downgraded. The acceptance is visible in the mapping; an
    info line every build is the same noise one rung down, and a notice nobody
    can resolve is a notice everyone learns to skim."""
    schema, bundle = _calculated_display_inputs(tmp_path, accepted=True)
    findings = validate_against_mapping(schema, bundle)
    none_of(findings, FindingCode.CALCULATED_DISPLAY_COLUMN_UNINDEXABLE)
    # Silent, not traded for a "you accepted this" notice of its own.
    none_of(findings, FindingCode.REDUNDANT_DISPLAY_COLUMN_ACCEPTANCE)

def _display_type_inputs(
    tmp_path: Path, column_type: str, *, looked_up: bool,
) -> tuple[Schema, MappingBundle]:
    follow_up = ["FollowUp"] if looked_up else []
    return pack(
        tmp_path,
        dbml=blocks(
            table("Event", ID_PK, "Title nvarchar", f"Notes {column_type}"),
            table("FollowUp", ID_PK, "Event int [ref: > Event.Id]") if looked_up else "",
        ),
        mapping=entities(entity("Event", display_column="Notes"), *follow_up),
    )

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
    f = only(
        validate_against_mapping(schema, bundle),
        FindingCode.DISPLAY_COLUMN_TYPE_UNINDEXABLE,
    )
    assert f.severity == "error"
    # The SharePoint type name, which is what the author sees in the UI.
    assert "Notes" in f.message and described_as in f.message

def test_an_unindexable_display_column_is_fine_when_nothing_looks_it_up(
    tmp_path: Path,
) -> None:
    """No lookup into it means no implicit index, so there is nothing to refuse.
    Erroring here would ban a perfectly good Note column from being the label a
    report happens to print."""
    schema, bundle = _display_type_inputs(tmp_path, "longtext", looked_up=False)
    none_of(
        validate_against_mapping(schema, bundle),
        FindingCode.DISPLAY_COLUMN_TYPE_UNINDEXABLE,
    )

def test_a_display_column_that_is_never_rendered_is_an_error(tmp_path: Path) -> None:
    """A cross-site logical column is declared in the DBML but replaced at deploy
    time by generated Abbreviation and SiteUrl fields, so it never exists on the
    list. _naming.py cannot see this — the name IS a declared column — and the
    implicit index would be created on a field that is not there."""
    schema, bundle = pack(
        tmp_path,
        dbml=blocks(
            table("Region", ID_PK, "Title nvarchar"),
            table("Event", ID_PK, "Title nvarchar", "Region int [ref: > Region.Id]"),
            table("FollowUp", ID_PK, "Event int [ref: > Event.Id]"),
        ),
        mapping="""
            entities:
              Region: { kind: List, base_template: 100, site_role: default }
              Event: { kind: List, base_template: 100, site_role: default, display_column: Region }
              FollowUp: { kind: List, base_template: 100, site_role: default }
            cross_site_reference_columns:
              - { entity: Event, column: Region }
        """,
    )
    f = only(
        validate_against_mapping(schema, bundle),
        FindingCode.DISPLAY_COLUMN_NOT_RENDERED,
    )
    assert f.severity == "error"
    # The hint that says WHERE the column went, not just that it is missing.
    assert "Abbreviation" in f.message

def test_a_pointless_acceptance_warns(tmp_path: Path) -> None:
    """Set where the display column is perfectly indexable, it signals a
    misunderstanding rather than a decision."""
    # The Event line is spelled block-style purely so it fits in 100 columns;
    # it parses to exactly the flow mapping every other entity here uses.
    schema, bundle = pack(
        tmp_path,
        dbml=blocks(
            table("Event", ID_PK, "Ref nvarchar"),
            table("FollowUp", ID_PK, "Event int [ref: > Event.Id]"),
        ),
        mapping="""
            entities:
              Event:
                kind: List
                base_template: 100
                site_role: default
                display_column: Ref
                accept_unindexable_display_column: true
              FollowUp: { kind: List, base_template: 100, site_role: default }
        """,
    )
    f = only(
        validate_against_mapping(schema, bundle),
        FindingCode.REDUNDANT_DISPLAY_COLUMN_ACCEPTANCE,
    )
    assert f.severity == "warning"
    # One code, several reasons: which one applies is only in the prose.
    assert "is not calculated" in f.message

def test_an_acceptance_on_an_unlooked_up_calculated_column_states_the_truth(
    tmp_path: Path,
) -> None:
    """Not a lookup target, display column IS calculated, key set. The verdict
    (remove it) is right, but the message used to say "the display column
    'Label' is not calculated" about a column that is. The combination had no
    test, which is why the false message shipped."""
    # Block style for the entity again, to stay inside 100 columns.
    schema, bundle = pack(
        tmp_path,
        dbml=table("Event", ID_PK, "Title nvarchar", "Label calculated_text"),
        mapping="""
            entities:
              Event:
                kind: List
                base_template: 100
                site_role: default
                display_column: Label
                accept_unindexable_display_column: true
            calculated_formulas:
              Event:
                Label: "=[Title]"
        """,
    )
    f = only(
        validate_against_mapping(schema, bundle),
        FindingCode.REDUNDANT_DISPLAY_COLUMN_ACCEPTANCE,
    )
    assert f.severity == "warning"
    assert "nothing looks this entity up" in f.message
    # 'Label' IS calculated. Saying otherwise is simply untrue.
    assert "is not calculated" not in f.message
