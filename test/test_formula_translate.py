"""Translated formulas against the reference evaluator, and every refusal."""

import pytest
from _format_eval import evaluate_expression
from _formula_grid import check_parity
from _node import NODE

from dbml_sharepoint.analysis.findings import FindingCode
from dbml_sharepoint.analysis.formula.functions import SUPPORTED, function_names
from dbml_sharepoint.analysis.formula.parse import parse_formula
from dbml_sharepoint.analysis.formula.refusal import FormulaRefusal
from dbml_sharepoint.analysis.formula.syntax import ColumnKind
from dbml_sharepoint.analysis.formula.translate import TranslationContext, translate_column

# Their parity cases are in test_formula_dates.py.
DATE_FUNCTIONS = {"DATE", "YEAR", "MONTH", "DAY"}

pytestmark = pytest.mark.skipif(NODE is None, reason="node is required")

KINDS: dict[str, ColumnKind] = {
    "Status": "choice",
    "Risk": "choice",
    "Name": "text",
    "Score": "number",
    "Due": "date",
    "Created": "date",
}
CHOICES = {"Status": ("Open", "Closed"), "Risk": ("Low", "High")}
# Two offsets from the site zone: the translation must not depend on the browser's zone.
BROWSERS = ("Australia/Melbourne", "America/Los_Angeles")
# Numbers come from chained calculated columns, because a stored number column is refused.
NUMBERS = {
    "Qty": 'IF([Status]="Open",3,IF([Status]="Closed",0-2,12))',
    "Price": 'IF([Risk]="High",0,IF([Risk]="Low",1,4))',
}

# id -> (formula, result type). One case per supported function and operator.
PARITY: dict[str, tuple[str, str]] = {
    "IF": ('IF([Qty]>2,"big","small")', "text"),
    "nested IF": ('IF([Status]="Open",IF([Risk]="High",3,2),1)', "number"),
    "AND": ('IF(AND([Qty]>1,[Price]<3),"y","n")', "text"),
    "OR": ('IF(OR([Qty]>5,[Price]<1),"y","n")', "text"),
    "NOT": ('IF(NOT([Qty]=12),"y","n")', "text"),
    "ISBLANK": ('IF(ISBLANK([Name]),"none",[Name])', "text"),
    "CHOOSE matrix": (
        'CHOOSE(IF([Status]="Open",1,2),CHOOSE(IF([Risk]="High",1,2),"a","b"),"c")',
        "text",
    ),
    "CHOOSE literal index": ('CHOOSE(2,"a",[Name],"c")', "text"),
    "MIN": ("MIN([Qty]+0,[Price]+0,5)", "number"),
    "MAX": ("MAX([Qty]+0,[Price]+0,5)", "number"),
    "ABS": ("ABS([Qty]-5)", "number"),
    "INT": ("INT([Qty]-5)", "number"),
    "ROUND": ("ROUND([Qty]*2,0)", "number"),
    "ampersand": ('[Name]&"-"&[Status]&5', "text"),
    "CONCATENATE": ('CONCATENATE([Name],"x",[Status])', "text"),
    "LEFT": ("LEFT([Name],2)", "text"),
    "LEFT default": ("LEFT([Name])", "text"),
    "MID": ("MID([Name],2,3)", "text"),
    "LOWER": ("LOWER([Name])", "text"),
    "UPPER": ("UPPER([Name])", "text"),
    "plus": ("[Qty]+[Price]", "number"),
    "minus": ("[Qty]-[Price]", "number"),
    "times": ("[Qty]*[Price]", "number"),
    "divide": ("[Qty]/([Price]+1)", "number"),
    "divide by a literal": ("[Qty]/4", "number"),
    "power": ("[Qty]^[Price]", "number"),
    "power negative exponent": ("[Qty]^(0-1)", "number"),
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
        formulas={"Calc": formula, **NUMBERS, **more},
        kinds=KINDS,
        result_types={
            "Calc": result,
            "Qty": "number",
            "Price": "number",
            "B": "number",
            "A": "number",
        },
        choices=CHOICES,
        zone="Australia/Melbourne",
    )


def _parity(formula: str, result: str, **more: str) -> str:
    ctx = _ctx(formula, result, **more)
    expression = translate_column("Calc", ctx).expression
    check_parity(formula, expression, ctx.formulas, KINDS, CHOICES, BROWSERS)
    return expression


def _run(expression: str, row: dict[str, object]) -> object:
    return evaluate_expression(expression, row, browser_tz="UTC", now="2026-10-20T12:00:00Z")


@pytest.mark.parametrize(("formula", "result"), PARITY.values(), ids=PARITY.keys())
def test_translation_matches_the_reference(formula: str, result: str) -> None:
    _parity(formula, result)


def test_every_supported_function_has_a_parity_case() -> None:
    exercised = set().union(*(function_names(parse_formula(f)) for f, _ in PARITY.values()))
    assert set(SUPPORTED) - exercised == DATE_FUNCTIONS


def test_text_equality_is_case_insensitive() -> None:
    assert _run(_parity('IF([Name]="ABC","y","n")', "text"), {"Name": "abc"}) == "y"


def test_blank_text_joins_as_empty() -> None:
    expression = _parity("[Name]&[Status]", "text")
    assert _run(expression, {"Name": "", "Status": ""}) == ""


def test_an_empty_result_hides() -> None:
    assert translate_column("Calc", _ctx('""', "text")).expression == "=''"


def test_a_chained_calculated_column_is_translated_in_place() -> None:
    expression = _parity("[B]*10", "number", B='IF([Status]="Open",1,2)')
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


# formula, result type, expected code, the function, operator or column the detail must name
REFUSED = [
    ("IF([Qty]>1,", "number", FindingCode.FORM_FORMULA_UNPARSEABLE, "position"),
    ('TRIM("  a   b  ")', "text", FindingCode.FORM_FORMULA_FUNCTION_UNSUPPORTED, "TRIM"),
    ("LEN([Name])", "number", FindingCode.FORM_FORMULA_FUNCTION_UNSUPPORTED, "LEN"),
    ("RIGHT([Name],2)", "text", FindingCode.FORM_FORMULA_FUNCTION_UNSUPPORTED, "RIGHT"),
    ("[Qty]+NOW()", "number", FindingCode.FORM_FORMULA_VOLATILE, "NOW"),
    ("[Owner]+1", "number", FindingCode.FORM_FORMULA_COLUMN_UNSUPPORTED, "Owner"),
    ("[Score]+1", "number", FindingCode.FORM_FORMULA_COLUMN_UNSUPPORTED, "Score"),
    ("[Qty]+1", "yesno", FindingCode.FORM_FORMULA_RESULT_UNSUPPORTED, "yesno"),
    ("[Qty]>1", "text", FindingCode.FORM_FORMULA_RESULT_UNSUPPORTED, "yes/no"),
    ("YEAR([Due])", "number", FindingCode.FORM_FORMULA_COLUMN_UNSUPPORTED, "Due"),
    ("[Due]", "date", FindingCode.FORM_FORMULA_COLUMN_UNSUPPORTED, "Due"),
    # A zero divisor, a zero or negative-power zero base and a negative base to a fraction are
    # column errors; the header would give Infinity or NaN instead.
    ("[Qty]/[Price]", "number", FindingCode.FORM_FORMULA_FUNCTION_UNSUPPORTED, "/"),
    ("[Qty]/0", "number", FindingCode.FORM_FORMULA_FUNCTION_UNSUPPORTED, "/"),
    ("[Qty]/([Price]-1)", "number", FindingCode.FORM_FORMULA_FUNCTION_UNSUPPORTED, "/"),
    ("[Price]^(0-1)", "number", FindingCode.FORM_FORMULA_FUNCTION_UNSUPPORTED, "^"),
    ("([Price]-1)^[Price]", "number", FindingCode.FORM_FORMULA_FUNCTION_UNSUPPORTED, "^"),
    ("[Price]^([Price]-1)", "number", FindingCode.FORM_FORMULA_FUNCTION_UNSUPPORTED, "^"),
    ("[Qty]^0.5", "number", FindingCode.FORM_FORMULA_FUNCTION_UNSUPPORTED, "^"),
    ("INT([Qty]/4)", "number", FindingCode.FORM_FORMULA_FUNCTION_UNSUPPORTED, "INT"),
    ("ROUND([Qty]/4,0)", "number", FindingCode.FORM_FORMULA_FUNCTION_UNSUPPORTED, "ROUND"),
    ("ROUND([Qty]+0,2)", "number", FindingCode.FORM_FORMULA_FUNCTION_UNSUPPORTED, "ROUND"),
    ("LEFT([Name],[Qty])", "text", FindingCode.FORM_FORMULA_FUNCTION_UNSUPPORTED, "LEFT"),
    ("ISBLANK([Qty])", "number", FindingCode.FORM_FORMULA_FUNCTION_UNSUPPORTED, "ISBLANK"),
    ('[Qty]&"x"', "text", FindingCode.FORM_FORMULA_FUNCTION_UNSUPPORTED, "&"),
    ('IF([Name]<"b",1,2)', "number", FindingCode.FORM_FORMULA_FUNCTION_UNSUPPORTED, "<"),
    ("IF([Qty]>1,1)", "number", FindingCode.FORM_FORMULA_FUNCTION_UNSUPPORTED, "IF"),
    ("[Name]+1", "number", FindingCode.FORM_FORMULA_FUNCTION_UNSUPPORTED, "+"),
    ('CHOOSE([Qty],"a","b")', "text", FindingCode.FORM_FORMULA_FUNCTION_UNSUPPORTED, "CHOOSE"),
    ('CHOOSE(1.5,"a","b")', "text", FindingCode.FORM_FORMULA_FUNCTION_UNSUPPORTED, "CHOOSE"),
    (
        'CHOOSE(IF([Qty]>1,1,1.5),"a","b")',
        "text",
        FindingCode.FORM_FORMULA_FUNCTION_UNSUPPORTED,
        "CHOOSE",
    ),
    ('CHOOSE(3,"a","b")', "text", FindingCode.FORM_FORMULA_FUNCTION_UNSUPPORTED, "CHOOSE"),
]


@pytest.mark.parametrize(("formula", "result", "code", "named"), REFUSED)
def test_a_refusal_names_the_formula_and_what_it_refused(
    formula: str, result: str, code: FindingCode, named: str
) -> None:
    refusal, message = _refusal(formula, result)
    assert refusal.code is code
    assert named in refusal.detail
    assert formula in message


# A quote has no documented escape inside an expression literal, in a plain or a table formula.
@pytest.mark.parametrize(
    "formula",
    ['"It\'s"', 'IF([Status]="O\'pen","a","b")', 'IF([Status]="Open","It\'s","b")', '[Name]&"\'"'],
)
def test_a_single_quote_in_a_text_is_refused(formula: str) -> None:
    with pytest.raises(FormulaRefusal) as found:
        translate_column("Calc", _ctx(formula, "text"))
    assert found.value.code is FindingCode.FORM_FORMULA_FUNCTION_UNSUPPORTED
    assert "single quote" in found.value.detail
