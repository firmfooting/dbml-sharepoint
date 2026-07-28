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


def test_risk_register_declares_its_five_working_views() -> None:
    """The default view is what everyone lands on, and the other four are
    the register's governance lenses. A view silently dropped leaves the
    list on SharePoint's untouched "All Items", which shows every column
    unsorted — and the build still exits 0."""
    views = _risk_bundle().mapping.views["Risk"]
    titles = [v.title for v in views]
    assert titles == [
        "Open by score", "Reviews due", "Above target",
        "Tolerance expiring", "Closed risks",
    ], titles
    default = [v for v in views if v.default]
    assert len(default) == 1 and default[0].title == "Open by score", (
        f"exactly one default view, and it must be the open-work view: {default}"
    )
    # Every view carries widths: SharePoint's own defaults truncate the
    # rating pills and the Title column at the widths this register needs.
    for view in views:
        assert view.widths, f"{view.title} declares no column widths"
        assert set(view.widths) <= set(view.fields), (
            f"{view.title} sets a width for a column it does not show: "
            f"{sorted(set(view.widths) - set(view.fields))}"
        )


def test_risk_register_demo_rows_cover_every_rating_band() -> None:
    """Demo data exists to make the views and formatting visible on a fresh
    site. A band with no row means the reviewer never sees that colour, that
    bar width or — for Extreme — the row wash at all, and nothing fails."""
    demo = _risk_bundle().mapping.demo_items["Risk"]
    keys = {row.key for row in demo}
    assert keys == {
        "risk-low", "risk-medium", "risk-high",
        "risk-extreme", "risk-tolerate", "risk-closed",
    }, sorted(keys)
    by_key = {row.key: row.values for row in demo}
    # Every Title carries the marker rollback.js trusts to delete demo-only
    # lists without the non-empty refusal.
    for key, values in by_key.items():
        assert values["Title"].startswith("[DEMO] "), f"{key} is not marked"
    # The tolerance view filters on ToleranceEndDate <= today+30, so the
    # Tolerate row must land inside that window or the view demos empty.
    assert by_key["risk-tolerate"]["RiskResponse"] == "Tolerate"
    assert by_key["risk-tolerate"]["ToleranceEndDate"] == "today+21"
    # The closed view and the closure-statement guidance both need this row.
    assert by_key["risk-closed"]["Status"] == "Closed"
    assert by_key["risk-closed"]["ClosureStatement"]
