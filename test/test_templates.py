# test/test_templates.py
"""Template-level regression tests.

The CI sweep proves every template BUILDS. It cannot prove a template
declares what it is supposed to declare — a view silently dropped, a
formula that lost its version guard, a demo row that no longer covers the
band it was written for. Those are invisible to a build that exits 0.
"""

from pathlib import Path

from dbml_sharepoint.analysis.validator import MAX_CALCULATED_FORMULA
from dbml_sharepoint.model.mapping_loader import MappingBundle, load_mapping
from dbml_sharepoint.model.parser import parse_dbml

RISK = Path(__file__).parent.parent / "templates" / "risk-register"


def _risk_bundle() -> MappingBundle:
    return load_mapping(RISK / "20-configure" / "mapping.yaml")


def test_risk_register_declares_the_governance_columns() -> None:
    """The uplift's whole point. A column silently absent takes its view
    column, its format and its form section down with it, and the build
    still exits 0 because nothing references what was never declared."""
    schema = parse_dbml(RISK / "10-design" / "schema.dbml")
    risk = next(t for t in schema.tables if t.name == "Risk")
    names = {c.name for c in risk.columns}
    for expected in (
        "ResidualRiskRating", "RiskScore", "TargetRiskRating", "LevelsAboveTarget",
        "RiskOwner", "RiskSponsor", "RiskResponse", "ToleranceEndDate",
        "OverallControlEffectiveness", "ClosureStatement", "NextReviewDue",
        "LastReviewedDate", "MatrixVersion", "SourceReference", "Treatment",
    ):
        assert expected in names, f"{expected} is not declared: {sorted(names)}"
    # Renamed and removed by the uplift; their old names must not linger.
    for gone in ("RiskRating", "Owner", "ReviewDate"):
        assert gone not in names, f"{gone} should have been renamed or removed"


def test_every_risk_formula_is_version_guarded_and_within_the_length_limit() -> None:
    """The MatrixVersion guard is the entire reason that column exists: it
    stops a matrix revision silently re-rating historical rows. A formula
    over the ceiling is refused by SharePoint part-way through provisioning,
    which a build cannot detect."""
    formulas = _risk_bundle().mapping.calculated_formulas["Risk"]
    assert set(formulas) == {
        "ResidualRiskRating", "RiskScore", "LevelsAboveTarget", "NextReviewDue",
    }, sorted(formulas)
    for name in ("ResidualRiskRating", "RiskScore"):
        assert '[MatrixVersion]<>"1.0"' in formulas[name], (
            f"{name} lost its matrix-version guard"
        )
    for name, formula in formulas.items():
        assert len(formula) <= MAX_CALCULATED_FORMULA, (
            f"{name} is {len(formula)} chars, over the {MAX_CALCULATED_FORMULA} ceiling"
        )
