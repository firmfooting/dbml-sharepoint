"""Validator: calculated columns, and a lookup target's display column."""
from pathlib import Path

import pytest
from _paths import FIXTURES
from _validator_helpers import _bundle_with_formulas, _schema

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
