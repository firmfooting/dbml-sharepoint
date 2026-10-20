"""Translated formulas against the reference evaluator, and every refusal."""

import pytest
from _format_eval import evaluate_expression
from _formula_grid import check_parity
from _node import NODE

from dbml_sharepoint.analysis.findings import FindingCode
from dbml_sharepoint.analysis.formula.functions import SUPPORTED, function_names
from dbml_sharepoint.analysis.formula.parse import parse_formula
from dbml_sharepoint.analysis.formula.syntax import ColumnKind
from dbml_sharepoint.analysis.formula.translate import (
    PENDING_DATES,
    FormulaRefusal,
    TranslationContext,
    translate_column,
)

pytestmark = pytest.mark.skipif(NODE is None, reason="node is required")

KINDS: dict[str, ColumnKind] = {
    "Status": "choice",
    "Risk": "choice",
    "Name": "text",
    "Qty": "number",
    "Price": "number",
    "Due": "date",
}
CHOICES = {"Status": ("Open", "Closed"), "Risk": ("Low", "High")}
BROWSERS = ("Australia/Melbourne",)

# id -> (formula, result type). One case per supported function and operator.
PARITY: dict[str, tuple[str, str]] = {
    "IF": ('IF([Qty]>2,"big","small")', "text"),
    "nested IF": ('IF([Status]="Open",IF([Risk]="High",3,2),1)', "number"),
    "AND OR NOT": ('IF(AND([Qty]>1,OR([Price]<3,NOT([Qty]=12))),"y","n")', "text"),
    "ISBLANK": ('IF(ISBLANK([Name]),"none",[Name])', "text"),
    "CHOOSE matrix": (
        'CHOOSE(IF([Status]="Open",1,2),CHOOSE(IF([Risk]="High",1,2),"a","b"),"c")',
        "text",
    ),
    "MIN": ("MIN([Qty]+0,[Price]+0,5)", "number"),
    "MAX": ("MAX([Qty]+0,[Price]+0,5)", "number"),
    "ABS": ("ABS([Qty]-5)", "number"),
    "INT": ("INT([Qty]/4)", "number"),
    "ROUND": ("ROUND(([Qty]+1)/2,0)", "number"),
    "ampersand": ('[Name]&"-"&[Status]&5', "text"),
    "CONCATENATE": ('CONCATENATE([Name],"x",[Status])', "text"),
    "LEFT": ("LEFT([Name],2)", "text"),
    "LEFT default": ("LEFT([Name])", "text"),
    "RIGHT": ("RIGHT([Name],2)", "text"),
    "RIGHT longer than text": ("RIGHT([Name],9)", "text"),
    "RIGHT zero": ("RIGHT([Name],0)", "text"),
    "MID": ("MID([Name],2,3)", "text"),
    "LEN": ("LEN([Name])", "number"),
    "LOWER": ("LOWER([Name])", "text"),
    "UPPER": ("UPPER([Name])", "text"),
    "plus": ("[Qty]+[Price]", "number"),
    "minus": ("[Qty]-[Price]", "number"),
    "times": ("[Qty]*[Price]", "number"),
    "divide": ("[Qty]/[Price]", "number"),
    "power": ("[Qty]^[Price]", "number"),
    "percent": ("[Qty]%*2", "number"),
    "negation": ("-[Qty]+1", "number"),
    "equal": ('IF([Qty]=[Price],"t","f")', "text"),
    "not equal": ('IF([Qty]<>[Price],"t","f")', "text"),
    "less": ('IF([Qty]<[Price],"t","f")', "text"),
    "greater": ('IF([Qty]>[Price],"t","f")', "text"),
    "less or equal": ('IF([Qty]<=[Price],"t","f")', "text"),
    "greater or equal": ('IF([Qty]>=[Price],"t","f")', "text"),
    "text equality": ('IF([Name]=[Status],"t","f")', "text"),
    "blank text joins as empty": ('"<"&[Name]&[Status]&">"', "text"),
    "empty result": ('""', "text"),
}


def _ctx(formula: str, result: str, **more: str) -> TranslationContext:
    return TranslationContext(
        formulas={"Calc": formula, **more},
        kinds=KINDS,
        result_types={"Calc": result, "B": "number", "C": "number", "A": "number"},
        choices=CHOICES,
        zone="Australia/Melbourne",
    )


def _parity(formula: str, result: str, **more: str) -> str:
    ctx = _ctx(formula, result, **more)
    expression = translate_column("Calc", ctx).expression
    check_parity(formula, expression, ctx.formulas, KINDS, CHOICES, BROWSERS)
    return expression


@pytest.mark.parametrize(("formula", "result"), PARITY.values(), ids=PARITY.keys())
def test_translation_matches_the_reference(formula: str, result: str) -> None:
    _parity(formula, result)


def test_every_supported_function_has_a_parity_case() -> None:
    exercised = set().union(*(function_names(parse_formula(f)) for f, _ in PARITY.values()))
    assert set(SUPPORTED) - exercised == PENDING_DATES


def test_text_equality_is_case_insensitive() -> None:
    expression = _parity('IF([Name]="ABC","y","n")', "text")
    row = {"Name": "abc"}
    assert evaluate_expression(expression, row, browser_tz="UTC", now="2026-10-20T12:00:00Z") == "y"


def test_blank_number_in_arithmetic_counts_as_zero() -> None:
    expression = _parity("[Qty]+1", "number")
    got = evaluate_expression(
        expression, {"Qty": None}, browser_tz="UTC", now="2026-10-20T12:00:00Z"
    )
    assert got == 1


def test_blank_text_joins_as_empty() -> None:
    expression = _parity("[Name]&[Status]", "text")
    row: dict[str, object] = {"Name": None, "Status": None}
    assert evaluate_expression(expression, row, browser_tz="UTC", now="2026-10-20T12:00:00Z") == ""


def test_an_empty_result_hides() -> None:
    assert translate_column("Calc", _ctx('""', "text")).expression == "=''"


def test_a_chained_calculated_column_is_translated_in_place() -> None:
    b, c = 'IF([Status]="Open",1,2)', "[B]*10"
    expression = _parity(c, "number", B=b)
    assert "$B" not in expression


def test_cycle_is_refused() -> None:
    ctx = _ctx("[A]+1", "number", A="[B]+1", B="[A]+1")
    with pytest.raises(FormulaRefusal) as found:
        translate_column("A", ctx)
    assert found.value.code is FindingCode.FORM_FORMULA_UNPARSEABLE
    assert "circular" in found.value.detail


def test_a_self_reference_is_refused() -> None:
    with pytest.raises(FormulaRefusal, match="refers back"):
        translate_column("A", _ctx("", "number", A="[A]+1"))


def _refusal(formula: str, result: str = "number") -> tuple[FormulaRefusal, str]:
    with pytest.raises(FormulaRefusal) as found:
        translate_column("Calc", _ctx(formula, result))
    return found.value, found.value.finding("Task", "Calc", formula).message


def test_unparseable_names_the_formula() -> None:
    refusal, message = _refusal("IF([Qty]>1,")
    assert refusal.code is FindingCode.FORM_FORMULA_UNPARSEABLE
    assert "IF([Qty]>1," in message


def test_unsupported_function_names_formula_and_function() -> None:
    refusal, message = _refusal('TRIM("  a   b  ")', "text")
    assert refusal.code is FindingCode.FORM_FORMULA_FUNCTION_UNSUPPORTED
    assert "TRIM" in message
    assert 'TRIM("  a   b  ")' in message


def test_volatile_names_formula_and_function() -> None:
    refusal, message = _refusal("[Qty]+NOW()")
    assert refusal.code is FindingCode.FORM_FORMULA_VOLATILE
    assert "NOW" in message
    assert "[Qty]+NOW()" in message


def test_an_unsupported_column_names_the_formula() -> None:
    refusal, message = _refusal("[Owner]+1")
    assert refusal.code is FindingCode.FORM_FORMULA_COLUMN_UNSUPPORTED
    assert "[Owner]+1" in message


def test_an_unsupported_result_names_the_formula() -> None:
    refusal, message = _refusal("[Qty]+1", "yesno")
    assert refusal.code is FindingCode.FORM_FORMULA_RESULT_UNSUPPORTED
    assert "[Qty]+1" in message


@pytest.mark.parametrize(
    "formula",
    ["DATE(2026,1,1)", "YEAR([Due])", "[Due]"],
)
def test_dates_are_refused_until_translated(formula: str) -> None:
    refusal, _ = _refusal(formula, "date")
    assert refusal.code is FindingCode.FORM_FORMULA_FUNCTION_UNSUPPORTED


@pytest.mark.parametrize(
    "formula",
    [
        "[Qty]",  # a bare number column: its blank cannot be told from 0
        "ROUND([Qty]+0,2)",
        "LEFT([Name],[Qty])",
        "ISBLANK([Qty])",
        '[Qty]&"x"',
        'IF([Name]<"b",1,2)',
        "IF([Qty]>1,1)",
        "[Name]+1",
    ],
)
def test_inexact_or_unmeasured_forms_are_refused(formula: str) -> None:
    result = "text" if formula.startswith(("LEFT", "[Qty]&")) else "number"
    refusal, _ = _refusal(formula, result)
    assert refusal.code.name.startswith("FORM_FORMULA_")
