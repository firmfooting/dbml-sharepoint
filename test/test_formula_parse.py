"""Parsing of SharePoint calculated-column formulas into a tree."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from dbml_sharepoint.analysis.column_refs import FORMULA_COLUMN_REF, formula_column_refs
from dbml_sharepoint.analysis.formula.functions import SUPPORTED, VOLATILE, function_names, refs
from dbml_sharepoint.analysis.formula.parse import parse_formula
from dbml_sharepoint.analysis.formula.syntax import (
    Binary,
    Call,
    Expr,
    FormulaSyntaxError,
    Neg,
    Num,
    Percent,
    Ref,
    Text,
)


def _n(value: float) -> Num:
    return Num(value)


# Operator order and left-to-right association follow Microsoft's "Calculation operators
# and precedence in Excel" (support.microsoft.com, id 48be406d-4975-4d31-b2b8-7af9e0e2878a):
# negation, %, ^, then * and /, then + and -, then &, then comparison. Microsoft's
# "Examples of common formulas in lists" says SharePoint formulas use Excel syntax but
# gives no precedence table of its own.
@pytest.mark.parametrize(
    ("formula", "expected"),
    [
        ("1+2*3", Binary("+", _n(1), Binary("*", _n(2), _n(3)))),
        ("(1+2)*3", Binary("*", Binary("+", _n(1), _n(2)), _n(3))),
        ("1-2-3", Binary("-", Binary("-", _n(1), _n(2)), _n(3))),
        ("8/4/2", Binary("/", Binary("/", _n(8), _n(4)), _n(2))),
        ("2^3^2", Binary("^", Binary("^", _n(2), _n(3)), _n(2))),
        ("1+2&3", Binary("&", Binary("+", _n(1), _n(2)), _n(3))),
        ('"a"&"b"="ab"', Binary("=", Binary("&", Text("a"), Text("b")), Text("ab"))),
        ("1<2=3>4", Binary(">", Binary("=", Binary("<", _n(1), _n(2)), _n(3)), _n(4))),
        ("1<=2<>3>=4", Binary(">=", Binary("<>", Binary("<=", _n(1), _n(2)), _n(3)), _n(4))),
        # Negation binds tighter than ^, so the base is negated first.
        ("-2^2", Binary("^", Neg(_n(2)), _n(2))),
        ("2^-2", Binary("^", _n(2), Neg(_n(2)))),
        ("-2*3", Binary("*", Neg(_n(2)), _n(3))),
        ("--2", Neg(Neg(_n(2)))),
        ("+2", _n(2)),
        # Percent binds tighter than ^, and applies to a negated operand.
        ("2^50%", Binary("^", _n(2), Percent(_n(50)))),
        ("50%*2", Binary("*", Percent(_n(50)), _n(2))),
        ("-5%", Percent(Neg(_n(5)))),
        ("5%%", Percent(Percent(_n(5)))),
    ],
)
def test_operator_precedence_and_associativity(formula: str, expected: Expr) -> None:
    assert parse_formula(formula) == expected


def test_percent_is_division_by_100_not_remainder() -> None:
    tree = parse_formula("[Rate]%")
    assert tree == Percent(Ref("Rate"))
    assert not isinstance(tree, Binary)
    with pytest.raises(FormulaSyntaxError):
        parse_formula("10%3")


def test_leading_equals_is_optional() -> None:
    assert parse_formula("=[A]+1") == parse_formula("[A]+1") == parse_formula("  = [A] + 1 ")


def test_numbers() -> None:
    assert parse_formula("1.5") == _n(1.5)
    assert parse_formula(".5") == _n(0.5)
    assert parse_formula("3.") == _n(3.0)


def test_doubled_quote_escapes_a_quote_in_a_literal() -> None:
    assert parse_formula('"say ""hi"""') == Text('say "hi"')
    assert parse_formula('""') == Text("")
    assert parse_formula('"a"&"""b"') == Binary("&", Text("a"), Text('"b'))


def test_brackets_inside_a_literal_are_not_references() -> None:
    tree = parse_formula('"[Not a ref]"&[Real]')
    assert refs(tree) == {"Real"}


def test_references_use_the_form_column_character_class() -> None:
    assert parse_formula("[Due date (2)]") == Ref("Due date (2)")
    assert parse_formula("[a-b_c.d]") == Ref("a-b_c.d")
    assert FORMULA_COLUMN_REF.fullmatch("[a-b_c.d]")
    for bad in ("[]", "[a[b]]", "[unclosed"):
        with pytest.raises(FormulaSyntaxError):
            parse_formula(bad)


def test_unbalanced_parenthesis_reports_the_position() -> None:
    with pytest.raises(FormulaSyntaxError) as missing_close:
        parse_formula("=1+(2*3")
    assert missing_close.value.position == 3
    with pytest.raises(FormulaSyntaxError) as stray_close:
        parse_formula("=1+2)")
    assert stray_close.value.position == 4
    with pytest.raises(FormulaSyntaxError) as call_open:
        parse_formula("IF([A]>1,2,3")
    assert call_open.value.position == 2


@pytest.mark.parametrize(
    "formula", ["", "=", "1+", "*2", "1 2", "[A]]", "FOO", "1 $ 2", "IF(1,)", "IF(,1)"]
)
def test_malformed_formulas_are_refused(formula: str) -> None:
    with pytest.raises(FormulaSyntaxError):
        parse_formula(formula)


def test_function_names_are_case_insensitive() -> None:
    tree = parse_formula('if(isblank([A]),"x",Upper([A]))')
    assert tree == Call("IF", (Call("ISBLANK", (Ref("A"),)), Text("x"), Call("UPPER", (Ref("A"),))))
    assert function_names(tree) == {"IF", "ISBLANK", "UPPER"}
    assert function_names(parse_formula("=IF(1,2,3)")) == function_names(
        parse_formula("=iF(1,2,3)")
    )


def test_calls_with_no_arguments_and_volatile_names() -> None:
    assert parse_formula("TODAY()") == Call("TODAY", ())
    assert function_names(parse_formula("[Due]-today()")) == VOLATILE & {"TODAY"}
    assert {"TODAY", "NOW"} == VOLATILE
    assert not VOLATILE & set(SUPPORTED)


def test_a_synthetic_month_end_formula_reads_as_nested_calls() -> None:
    tree = parse_formula("=DATE(YEAR([Start]),MONTH([Start])+[Months],MIN(DAY([Start]),28))")
    assert function_names(tree) == {"DATE", "YEAR", "MONTH", "MIN", "DAY"}
    assert refs(tree) == {"Start", "Months"}
    assert function_names(tree) <= set(SUPPORTED)


def test_supported_argument_counts_are_ordered() -> None:
    for low, high in SUPPORTED.values():
        assert low >= 0
        assert high is None or high >= low


_NAME_CHARS = st.characters(blacklist_characters='[]"\n\r', blacklist_categories=("Cs", "Cc"))
_names = st.text(_NAME_CHARS, min_size=1, max_size=8).filter(lambda s: s.strip() == s)
_literal_text = st.text(st.characters(blacklist_categories=("Cs", "Cc")), max_size=8)


def _quote(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


_leaves = st.one_of(
    st.integers(0, 99).map(str),
    _literal_text.map(_quote),
    _names.map(lambda n: f"[{n}]"),
)


def _grow(children: st.SearchStrategy[str]) -> st.SearchStrategy[str]:
    binary = st.tuples(
        children, st.sampled_from(["+", "-", "*", "/", "^", "&", "=", "<>", "<="]), children
    ).map(lambda t: f"({t[0]}{t[1]}{t[2]})")
    call = st.tuples(
        st.sampled_from(["if", "AND", "Concatenate", "MAX", "today"]),
        st.lists(children, max_size=3),
    ).map(lambda t: f"{t[0]}({','.join(t[1])})")
    unary = st.tuples(st.sampled_from(["-", "+"]), children).map(lambda t: f"{t[0]}({t[1]})")
    percent = children.map(lambda c: f"({c})%")
    return st.one_of(binary, call, unary, percent)


@given(st.recursive(_leaves, _grow, max_leaves=8))
def test_refs_agree_with_formula_column_refs(formula: str) -> None:
    assert refs(parse_formula(formula)) == formula_column_refs(formula)
