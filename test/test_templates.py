# test/test_templates.py
"""Template-level regression tests.

The CI sweep proves every template BUILDS. It cannot prove a template
declares what it is supposed to declare — a view silently dropped, a
formula that lost its version guard, a demo row that no longer covers the
band it was written for. Those are invisible to a build that exits 0.
"""

from pathlib import Path

from dbml_sharepoint.analysis.validator import MAX_CALCULATED_FORMULA
from dbml_sharepoint.generators.jsgen import _rewrite_formula_refs
from dbml_sharepoint.model.mapping_loader import MappingBundle, load_mapping
from dbml_sharepoint.model.parser import parse_dbml

RISK = Path(__file__).parent.parent / "templates" / "risk-register"


def _risk_bundle() -> MappingBundle:
    return load_mapping(RISK / "20-configure" / "mapping.yaml")


def _choose_call_args(formula: str) -> list[str]:
    """Split the top-level arguments out of a formula's (single) CHOOSE(...)
    call, respecting nested parens and quoted strings — so a demo-row band
    check can read the SHIPPED formula's own 25-cell array instead of a
    second copy of the matrix that could drift from it independently."""
    start = formula.index("CHOOSE(") + len("CHOOSE(")
    depth = 1
    args: list[str] = []
    current: list[str] = []
    in_quote = False
    i = start
    while depth > 0:
        ch = formula[i]
        if in_quote:
            current.append(ch)
            if ch == '"':
                in_quote = False
        elif ch == '"':
            in_quote = True
            current.append(ch)
        elif ch == "(":
            depth += 1
            current.append(ch)
        elif ch == ")":
            depth -= 1
            if depth == 0:
                args.append("".join(current))
                break
            current.append(ch)
        elif ch == "," and depth == 1:
            args.append("".join(current))
            current = []
        else:
            current.append(ch)
        i += 1
    return args


def _unquote(literal: str) -> str:
    stripped = literal.strip()
    assert stripped.startswith('"') and stripped.endswith('"'), (
        f"expected a quoted CHOOSE argument, got {literal!r}"
    )
    return stripped[1:-1]


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
    which a build cannot detect. SharePoint receives formulas AFTER
    display-name rewriting (internal names are rewritten to display titles
    at build time — see jsgen._rewrite_formula_refs), and a rewritten
    formula is longer than the authored one, so the ceiling is checked
    against the rewritten string, not the authored one."""
    bundle = _risk_bundle()
    formulas = bundle.mapping.calculated_formulas["Risk"]
    assert set(formulas) == {
        "ResidualRiskRating", "RiskScore", "LevelsAboveTarget", "NextReviewDue",
    }, sorted(formulas)
    for name in ("ResidualRiskRating", "RiskScore"):
        assert '[MatrixVersion]<>"1.0"' in formulas[name], (
            f"{name} lost its matrix-version guard"
        )
    schema = parse_dbml(RISK / "10-design" / "schema.dbml")
    risk = next(t for t in schema.tables if t.name == "Risk")
    display_map = {
        c.name: bundle.mapping.display_name_for("Risk", c.name) for c in risk.columns
    }
    for name, formula in formulas.items():
        rewritten = _rewrite_formula_refs(formula, display_map)
        assert len(rewritten) <= MAX_CALCULATED_FORMULA, (
            f"{name} is {len(rewritten)} chars after display-name rewriting "
            f"(SharePoint's own formula), over the {MAX_CALCULATED_FORMULA} ceiling"
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

    # Band coverage, checked against the SHIPPED ResidualRiskRating formula
    # rather than a duplicate of the matrix: resolve each row's
    # Likelihood/Consequence through the formula's own 25-cell CHOOSE
    # array, so a future edit that shifts risk-high's inputs onto a
    # different cell is caught here even though the key still says "high".
    schema = parse_dbml(RISK / "10-design" / "schema.dbml")
    likelihood_order = next(e.members for e in schema.enums if e.name == "risk_likelihood")
    consequence_order = next(e.members for e in schema.enums if e.name == "risk_consequence")
    formula = _risk_bundle().mapping.calculated_formulas["Risk"]["ResidualRiskRating"]
    choose_args = _choose_call_args(formula)
    bands = [_unquote(arg) for arg in choose_args[1:]]
    assert len(bands) == 25, f"expected a 25-cell CHOOSE array, got {len(bands)}: {bands}"

    def resolved_band(likelihood: str, consequence: str) -> str:
        li = likelihood_order.index(likelihood) + 1
        ci = consequence_order.index(consequence) + 1
        return bands[(li - 1) * 5 + (ci - 1)]

    resolved = {
        key: resolved_band(values["Likelihood"], values["Consequence"])
        for key, values in by_key.items()
    }
    for key, expected_band in (
        ("risk-low", "Low"), ("risk-medium", "Medium"),
        ("risk-high", "High"), ("risk-extreme", "Extreme"),
    ):
        assert resolved[key] == expected_band, (
            f"{key}: Likelihood={by_key[key]['Likelihood']!r} Consequence="
            f"{by_key[key]['Consequence']!r} resolves to {resolved[key]!r} "
            f"via the shipped formula, not {expected_band!r}"
        )
    assert set(resolved.values()) >= {"Low", "Medium", "High", "Extreme"}, (
        f"only {sorted(set(resolved.values()))} of the four rating bands "
        f"are covered by the demo rows: {resolved}"
    )
