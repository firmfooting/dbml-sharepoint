"""Validator: the `default_formulas` section.

A default formula is the one field property this tool writes that SharePoint
evaluates on its own clock, at row creation, so nothing in the build can
check its result. The rules here are what stands between an author and a
formula that saves clean and fills nothing.
"""

import pytest
from _findings import by_severity, codes, none_of, only
from _model import bundle as make_bundle
from _model import column, enum, person
from _model import ref as make_ref
from _model import schema as make_schema
from _model import table as make_table

from dbml_sharepoint.analysis.checks import _default_formulas
from dbml_sharepoint.analysis.checks._default_formulas import (
    DEFAULT_FORMULA_FUNCTIONS,
    DEFAULT_FORMULA_TYPES,
    ENUM,
    PENDING_DEFAULT_FORMULA_TYPES,
)
from dbml_sharepoint.analysis.column_refs import formula_function_names
from dbml_sharepoint.analysis.findings import Finding, FindingCode, Section
from dbml_sharepoint.analysis.validator import validate_against_mapping
from dbml_sharepoint.model.mapping_types import CrossSiteRef
from dbml_sharepoint.model.parser import Schema

_DEFAULT_FORMULA_CODES = frozenset(
    code for code in FindingCode if code.name.startswith("DEFAULT_FORMULA_")
)


def _schema() -> Schema:
    return make_schema(
        make_table(
            "Saq",
            column("Title", required=True),
            column("PeriodYear", "int"),
            column("Score", "number"),
            column("Quarter", "quarter"),
            column("Tags", "quarter[]"),
            column("Due", "date"),
            column("Opened", "datetime"),
            column("Ref", "nvarchar"),
            column("Closed", "boolean"),
            column("Notes", "longtext"),
            column("Link", "hyperlink"),
            person("Owner"),
            make_ref("Parent", "Saq.Id"),
            column("Band", "calculated_text"),
            column("Seeded", "nvarchar", default="x"),
            note="The standard fixture list.",
        ),
        enums=[enum("quarter", "Q1", "Q2", "Q3", "Q4")],
    )


def _findings(formulas: dict[str, str], **sections: object) -> list[Finding]:
    bundle = make_bundle(
        entities=["Saq"],
        default_formulas={"Saq": formulas},
        calculated_formulas={"Saq": {"Band": '="x"'}},
        **sections,  # type: ignore[arg-type]
    )
    return validate_against_mapping(_schema(), bundle)


def _own(findings: list[Finding]) -> list[Finding]:
    """Only this section's findings, so an unrelated rule cannot mask one."""
    return [f for f in findings if f.code in _DEFAULT_FORMULA_CODES]


# --- accepted declarations --------------------------------------------------


@pytest.mark.parametrize("col", ["PeriodYear", "Score", "Due", "Opened"])
def test_a_formula_on_a_measured_scalar_type_is_accepted(col: str) -> None:
    assert _own(_findings({col: "=YEAR(TODAY())"})) == []


def test_the_brief_s_own_examples_are_accepted() -> None:
    findings = _findings({
        "PeriodYear": "=YEAR(TODAY())",
        "Quarter": '="Q"&ROUNDUP(MONTH(TODAY())/3,0)',
    })
    assert by_severity(_own(findings), "error") == []


def test_an_enum_column_is_accepted_with_a_warning_about_the_result() -> None:
    """Measured 2026-09-13: a non-member result is stored as a literal."""
    findings = _own(_findings({"Quarter": '="Q"&ROUNDUP(MONTH(TODAY())/3,0)'}))
    warning = only(findings, FindingCode.DEFAULT_FORMULA_CHOICE_RESULT_UNCHECKED)
    assert warning.severity == "warning"
    assert "quarter" in warning.message
    assert "literal" in warning.message
    assert by_severity(findings, "error") == []


def test_the_section_is_optional() -> None:
    bundle = make_bundle(entities=["Saq"], calculated_formulas={"Saq": {"Band": '="x"'}})
    assert _own(validate_against_mapping(_schema(), bundle)) == []


# --- the formula's text -----------------------------------------------------


def test_a_formula_without_a_leading_equals_is_refused() -> None:
    finding = only(_findings({"Due": "TODAY()"}), FindingCode.DEFAULT_FORMULA_MISSING_EQUALS)
    assert finding.location is not None
    assert finding.location.section is Section.DEFAULT_FORMULAS
    assert finding.location.entity == "Saq"
    assert finding.location.column == "Due"


@pytest.mark.parametrize("formula", ["=[Created]", "=YEAR([Due])", "=[Today]"])
def test_a_formula_naming_a_column_is_refused(formula: str) -> None:
    finding = only(
        _findings({"Due": formula}), FindingCode.DEFAULT_FORMULA_REFERENCES_A_COLUMN,
    )
    assert "before the row exists" in finding.message


def test_bracket_text_inside_a_string_literal_is_not_a_reference() -> None:
    none_of(
        _findings({"Ref": '="[not a column]"'}),
        FindingCode.DEFAULT_FORMULA_REFERENCES_A_COLUMN,
    )


@pytest.mark.parametrize("formula", ["=NOW()", "=today()", "=DATE(2026,1,1)"])
def test_a_function_outside_the_allowlist_is_refused(formula: str) -> None:
    finding = only(
        _findings({"Due": formula}), FindingCode.DEFAULT_FORMULA_FUNCTION_UNSUPPORTED,
    )
    assert "TODAY" in finding.message


def test_every_allowed_function_passes_the_function_rule() -> None:
    formula = "=" + "&".join(f"{name}(1)" for name in sorted(DEFAULT_FORMULA_FUNCTIONS))
    none_of(_findings({"Ref": formula}), FindingCode.DEFAULT_FORMULA_FUNCTION_UNSUPPORTED)


def test_a_function_name_inside_a_string_literal_is_not_a_call() -> None:
    none_of(
        _findings({"Ref": '="NOW("&TEXT(TODAY(),"yyyy")'}),
        FindingCode.DEFAULT_FORMULA_FUNCTION_UNSUPPORTED,
    )


def test_the_function_parser_reads_calls_outside_literals_only() -> None:
    assert formula_function_names('="IF("&ROUNDUP(MONTH(TODAY())/3,0)') == frozenset({
        "ROUNDUP", "MONTH", "TODAY",
    })
    assert formula_function_names("=1+2") == frozenset()
    assert formula_function_names('="a ""quoted"" x"&today( )') == frozenset({"today"})


# --- the column ------------------------------------------------------------


def test_a_column_the_entity_does_not_declare_is_refused() -> None:
    finding = only(
        _findings({"Missing": "=TODAY()"}), FindingCode.DEFAULT_FORMULA_UNKNOWN_COLUMN,
    )
    assert "Missing" in finding.message
    assert finding.location is not None
    assert finding.location.column == "Missing"


def test_the_identity_column_is_not_one_the_deploy_creates() -> None:
    only(_findings({"Id": "=1"}), FindingCode.DEFAULT_FORMULA_UNKNOWN_COLUMN)


def test_a_formula_beside_a_dbml_default_is_refused() -> None:
    finding = only(
        _findings({"Seeded": '="x"'}), FindingCode.DEFAULT_FORMULA_BESIDE_A_DEFAULT_VALUE,
    )
    assert "default: 'x'" in finding.message


@pytest.mark.parametrize(
    ("col", "reason"),
    [
        ("Title", "built-in Title"),
        ("Band", "calculated"),
        ("Tags", "multi-value"),
        ("Owner", "Person"),
        ("Link", "Hyperlink"),
        ("Parent", "Lookup"),
    ],
)
def test_a_column_kind_that_cannot_take_a_formula_is_refused(col: str, reason: str) -> None:
    finding = only(
        _findings({col: "=TODAY()"}), FindingCode.DEFAULT_FORMULA_COLUMN_KIND_UNSUPPORTED,
    )
    assert reason in finding.message
    assert finding.location is not None
    assert finding.location.column == col


def test_a_cross_site_reference_column_is_refused_by_kind() -> None:
    findings = _findings(
        {"Parent": "=TODAY()"},
        cross_site_reference_columns=[CrossSiteRef(entity="Saq", column="Parent")],
    )
    finding = only(findings, FindingCode.DEFAULT_FORMULA_COLUMN_KIND_UNSUPPORTED)
    assert "cross-site" in finding.message


def test_an_unmeasured_type_is_refused_as_pending() -> None:
    finding = only(_findings({"Ref": '="x"'}), FindingCode.DEFAULT_FORMULA_TYPE_UNMEASURED)
    assert "not been measured" in finding.message
    assert "nvarchar" in finding.message


@pytest.mark.parametrize("col", ["Closed", "Notes"])
def test_a_type_nothing_plans_to_measure_is_refused_outright(col: str) -> None:
    finding = only(
        _findings({col: "=TODAY()"}), FindingCode.DEFAULT_FORMULA_TYPE_UNSUPPORTED,
    )
    assert "single-value enum" in finding.message


def test_the_kind_rule_wins_over_the_type_rule() -> None:
    """A multi-value enum is refused by arity, not by its enum's name."""
    findings = _own(_findings({"Tags": '="Q1"'}))
    assert codes(findings) == {FindingCode.DEFAULT_FORMULA_COLUMN_KIND_UNSUPPORTED}


def test_the_text_rules_and_the_column_rules_report_together() -> None:
    findings = _own(_findings({"Notes": "NOW()"}))
    assert codes(findings) == {
        FindingCode.DEFAULT_FORMULA_MISSING_EQUALS,
        FindingCode.DEFAULT_FORMULA_FUNCTION_UNSUPPORTED,
        FindingCode.DEFAULT_FORMULA_TYPE_UNSUPPORTED,
    }


def test_an_unknown_entity_is_reported_under_this_section() -> None:
    bundle = make_bundle(
        entities=["Saq"],
        default_formulas={"Nope": {"Due": "=TODAY()"}},
        calculated_formulas={"Saq": {"Band": '="x"'}},
    )
    findings = [
        f for f in validate_against_mapping(_schema(), bundle)
        if f.location is not None and f.location.section is Section.DEFAULT_FORMULAS
    ]
    finding = only(findings, FindingCode.UNKNOWN_ENTITY)
    assert finding.location is not None
    assert finding.location.entity == "Nope"


# --- the one switch ---------------------------------------------------------


def test_the_accepted_and_pending_sets_do_not_overlap() -> None:
    assert not DEFAULT_FORMULA_TYPES & PENDING_DEFAULT_FORMULA_TYPES
    assert ENUM in DEFAULT_FORMULA_TYPES


def test_widening_the_constant_is_the_whole_change(monkeypatch: pytest.MonkeyPatch) -> None:
    """The probe that measures `nvarchar` lands by editing one line."""
    monkeypatch.setattr(
        _default_formulas, "DEFAULT_FORMULA_TYPES", DEFAULT_FORMULA_TYPES | {"nvarchar"},
    )
    assert _own(_findings({"Ref": '="x"'})) == []
