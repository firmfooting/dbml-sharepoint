"""Choice-only sub-formulas become nested tables, with parity over the full grid."""

import pytest
from _format_eval import evaluate_expression
from _formula_grid import check_parity
from _node import NODE

from dbml_sharepoint.analysis.findings import FindingCode
from dbml_sharepoint.analysis.formula.parse import parse_formula
from dbml_sharepoint.analysis.formula.refusal import FormulaRefusal, check_size
from dbml_sharepoint.analysis.formula.syntax import ColumnKind
from dbml_sharepoint.analysis.formula.translate import (
    TranslationContext,
    tabulate,
    translate_column,
)
from dbml_sharepoint.analysis.limits import FORM_HEADER_MAX_CHARS

pytestmark = pytest.mark.skipif(NODE is None, reason="node is required")

KINDS: dict[str, ColumnKind] = {"Status": "choice", "Risk": "choice", "Name": "text", "Due": "date"}
CHOICES = {"Status": ("A", "B", "C", "D"), "Risk": ("W", "X", "Y", "Z")}
BROWSERS = ("Australia/Melbourne", "America/Los_Angeles", "UTC", "Pacific/Auckland")
NOW = "2026-10-20T12:00:00Z"


def _ladder(column: str, letters: str) -> str:
    # 1 to 4 for the four listed letters, 5 for anything else.
    text = "5"
    for number, letter in reversed(list(enumerate(letters, 1))):
        text = f'IF([{column}]="{letter}",{number},{text})'
    return text


def _matrix(cell: str) -> str:
    rows = ",".join(
        f"CHOOSE({_ladder('Risk', 'WXYZ')},{','.join(cell.format(r, c) for c in range(1, 6))})"
        for r in range(1, 6)
    )
    return f"CHOOSE({_ladder('Status', 'ABCD')},{rows})"


def _ctx(formula: str, result: str) -> TranslationContext:
    return TranslationContext(
        formulas={"Calc": formula},
        kinds=KINDS,
        result_types={"Calc": result},
        choices=CHOICES,
        zone="Australia/Melbourne",
    )


def _parity(formula: str, result: str = "text") -> str:
    ctx = _ctx(formula, result)
    expression = translate_column("Calc", ctx).expression
    check_parity(formula, expression, ctx.formulas, KINDS, CHOICES, BROWSERS)
    return expression


def _tabulated(formula: str, result: str = "text") -> str | None:
    return tabulate(parse_formula(formula), _ctx(formula, result))


def _run(expression: str, row: dict[str, object]) -> object:
    return evaluate_expression(expression, row, browser_tz="UTC", now=NOW)


def test_a_choice_matrix_becomes_depth_two() -> None:
    formula = _matrix('"r{}c{}"')
    expression = _parity(formula)
    # Status is tested once per listed value at the outer level, Risk inside each of its five arms.
    assert expression.count("[$Status]") == 4
    assert expression.count("[$Risk]") == 4 * 5
    assert expression.count("'r") == 25
    assert _tabulated(formula) is not None


def test_a_choice_used_with_a_substring_function_is_not_tabulated() -> None:
    formula = 'IF(LEFT([Status],1)="A","y","n")'
    assert _tabulated(formula) is None
    _parity(formula)


def test_a_choice_compared_with_another_column_is_not_tabulated() -> None:
    formula = 'IF([Status]=[Risk],"y","n")'
    assert _tabulated(formula) is None
    _parity(formula)


def test_a_sub_formula_with_a_non_choice_input_is_not_tabulated() -> None:
    formula = 'IF([Status]="A",[Name],"x")'
    assert _tabulated(formula) is None
    _parity(formula)


def test_case_variants_take_the_literal_branch() -> None:
    expression = _parity('IF([Status]="A","literal","other")')
    assert [_run(expression, {"Status": s}) for s in ("a", "A", "b", "")] == [
        "literal",
        "literal",
        "other",
        "other",
    ]


@pytest.mark.parametrize(
    ("formula", "unlisted"),
    [
        ('IF([Status]<>"A","not a","is a")', "not a"),
        ('IF("A"=[Status],"is a","not a")', "not a"),
        ('IF(AND([Status]<>"A",[Status]<>"B"),"neither","some")', "neither"),
        ('IF(OR([Status]="A",[Status]="B"),"listed","unlisted")', "unlisted"),
    ],
)
def test_unlisted_value_takes_the_formulas_own_result(formula: str, unlisted: str) -> None:
    expression = _parity(formula)
    # Parity over the grid is the proof; these are the unlisted and blank rows by name.
    assert _run(expression, {"Status": "zzz"}) == unlisted
    assert _run(expression, {"Status": ""}) == unlisted


def test_a_mixed_result_is_still_refused() -> None:
    with pytest.raises(FormulaRefusal) as found:
        translate_column("Calc", _ctx('IF([Status]="A",1,"x")', "text"))
    assert found.value.code is FindingCode.FORM_FORMULA_UNPARSEABLE


def test_the_chained_rating_stays_under_budget() -> None:
    chain = {"Rating": _matrix("{}+{}"), "Start": "DATE(2026,[Rating],1)", "End": "[Start]+30"}
    formula = "DAY([End])+MONTH([End])*100+DAY([Start])*10000"
    ctx = TranslationContext(
        formulas={"Calc": formula, **chain},
        kinds=KINDS,
        result_types={"Calc": "number", "Rating": "number", "Start": "date", "End": "date"},
        choices=CHOICES,
        zone="Australia/Melbourne",
    )
    expression = translate_column("Calc", ctx).expression
    check_parity(formula, expression, ctx.formulas, KINDS, CHOICES, BROWSERS)
    assert len(expression) < FORM_HEADER_MAX_CHARS


def test_over_budget_is_refused_naming_the_column() -> None:
    check_size("Task", "Rating", "x" * FORM_HEADER_MAX_CHARS)
    with pytest.raises(FormulaRefusal) as found:
        check_size("Task", "Rating", "x" * (FORM_HEADER_MAX_CHARS + 1))
    assert found.value.code is FindingCode.FORM_HEADER_TOO_LARGE
    assert "Task.Rating" in found.value.detail
    assert str(FORM_HEADER_MAX_CHARS + 1) in found.value.detail
    assert "Task.Rating" in found.value.finding("Task", "Rating", "F").message
