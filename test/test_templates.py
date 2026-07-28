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


def _condition_fields(node: object) -> set[str]:
    """Every column a condition tree reads, at any nesting depth.

    The grammar's nodes are a Leaf/Group union, and a group may hold
    groups — so walking beats indexing `.children` and assuming one level.
    """
    children = getattr(node, "children", None)
    if children is not None:
        return {name for child in children for name in _condition_fields(child)}
    field = getattr(node, "field", None)
    return {field} if isinstance(field, str) else set()


def _condition_ops(node: object) -> set[str]:
    """Every operator a condition tree uses, at any nesting depth."""
    children = getattr(node, "children", None)
    if children is not None:
        return {op for child in children for op in _condition_ops(child)}
    op = getattr(node, "op", None)
    return {op} if isinstance(op, str) else set()


def test_risk_register_shows_conditional_fields_only_when_they_apply() -> None:
    """The form asks for what the answer implies, and nothing else.

    Two of these pair a visibility rule with a save rule, and the pairing
    is the point: `ToleranceEndDate` is mandatory exactly when the response
    is Tolerate, so showing it any other time produces a field nobody needs
    and a rejection whose cause is off-screen. Drop the visibility rule and
    the save rule starts firing on forms that never displayed the column it
    names — which is how a list stops accepting rows for reasons its
    authors cannot see.
    """
    columns = _risk_bundle().mapping.form_visibility["Risk"].columns

    tolerance = columns["ToleranceEndDate"]
    assert tolerance.when is not None, (
        "ToleranceEndDate must be conditional, not always shown"
    )
    fields = _condition_fields(tolerance.when)
    assert fields == {"RiskResponse"}, (
        f"the tolerance date is gated on the response, not {sorted(fields)}"
    )

    # Nobody closes a risk at creation, so this is off New entirely AND
    # gated on Status once the item exists. Both halves matter.
    closure = columns["ClosureStatement"]
    assert closure.new is False, "ClosureStatement must not appear on the New form"
    assert closure.when is not None, "ClosureStatement must be gated on Status"
    assert _condition_fields(closure.when) == {"Status"}, (
        "ClosureStatement must be gated on Status"
    )

    # Auto-stamped at creation by its own default; visible afterwards so a
    # completed review can move it forward.
    assert columns["LastReviewedDate"].new is False
    assert columns["LastReviewedDate"].existing is True

    # A calculated column can never carry a visibility rule (the build
    # rejects it) and never renders on an entry form, so none may appear.
    calculated = {"ResidualRiskRating", "RiskScore", "LevelsAboveTarget", "NextReviewDue"}
    assert not (calculated & set(columns)), (
        f"calculated columns cannot have form visibility: {sorted(calculated & set(columns))}"
    )


def test_risk_register_save_rules_split_by_what_they_can_reference() -> None:
    """Column rules self-reference; the one list rule is cross-column.

    SharePoint gives a column a single ValidationFormula and a LIST a
    single ValidationFormula. So every cross-column rule competes for one
    slot and one message, while per-column rules each keep their own. A
    self-referencing rule that drifts into `list_validation` costs the
    template the message that told someone which rule they broke.
    """
    mapping = _risk_bundle().mapping

    col_rules = mapping.column_validation["Risk"].columns
    assert "LastReviewedDate" in col_rules, (
        "the future-date guard is gone; a mistyped year silently pushes "
        "NextReviewDue out and drops the risk off the review views"
    )
    rule = col_rules["LastReviewedDate"]
    assert _condition_fields(rule.when) == {"LastReviewedDate"}, (
        "a column rule may reference only its own column — SharePoint "
        "refuses anything else, so this belongs in list_validation"
    )
    assert rule.message, "a rule with no message fails with SharePoint's generic text"

    # Admits a blank on purpose: the column is hidden from the New form and
    # filled by its [today] default, and a rule that cannot pass with it
    # empty would reject every new item if that ever stopped holding.
    assert "is_null" in _condition_ops(rule.when), (
        "the rule must admit an empty date, or a create with no default "
        "rejects every new risk"
    )

    # The single list slot carries all three cross-column rules, chained.
    list_rule = mapping.list_validation["Risk"]
    assert _condition_fields(list_rule.when) == {
        "RiskResponse", "ToleranceEndDate",       # Tolerate needs its end date
        "Status", "Likelihood", "Consequence",    # past Provisional means assessed
        "OverallControlEffectiveness",            # Closed needs controls that hold
    }, "a chained list rule was dropped, or a self-referencing one crept in"
    # Every operand is a type SharePoint can actually read in a validation
    # formula. Person, calculated and multi-line columns are refused at
    # build time, so a rule reaching for RiskOwner or ClosureStatement is a
    # rule that cannot exist — worth failing here with the reason.
    schema = parse_dbml(RISK / "10-design" / "schema.dbml")
    types = {c.name: c.type for c in next(
        t for t in schema.tables if t.name == "Risk").columns}
    unusable = {"person", "richtext", "longtext",
                "calculated_text", "calculated_number", "calculated_date"}
    for name in _condition_fields(list_rule.when):
        assert types[name] not in unusable, (
            f"{name} is {types[name]}, which SharePoint cannot read in a "
            f"validation formula"
        )


def test_risk_register_demo_rows_satisfy_every_save_rule() -> None:
    """Seeded rows are written by deploy, so a rule they break is a rule
    that breaks the demo — and `--seed` is how a reviewer first sees the
    template work. The chained list rule made this reachable: adding a
    cross-column rule can retrospectively invalidate demo data written
    before it existed, and nothing else would catch that until a paste."""
    bundle = _risk_bundle()
    closure_ok = {"Eliminated or within appetite", "All reasonable controls in place"}
    for row in bundle.mapping.demo_items["Risk"]:
        v = row.values
        assert v.get("RiskResponse") != "Tolerate" or v.get("ToleranceEndDate"), (
            f"{row.key}: tolerates without an end date"
        )
        assert v.get("Status") == "Provisional" or (
            v.get("Likelihood") and v.get("Consequence")
        ), f"{row.key}: past Provisional without being assessed"
        assert v.get("Status") != "Closed" or (
            v.get("OverallControlEffectiveness") in closure_ok
        ), f"{row.key}: closed without controls that hold"
