"""Translate a calculated column's formula into a column-formatting expression.

The expression is what a form header evaluates in place of the column, because a header reads a
calculated column as blank. Anything the formatting language cannot reproduce exactly is refused
by name; a header that could differ from its column on one row is a failed build.

Formatting functions used here are listed on the formatting syntax reference (Microsoft Learn,
https://learn.microsoft.com/en-us/sharepoint/dev/declarative-customization/formatting-syntax-reference),
each cited where it is emitted.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal, NoReturn

from dbml_sharepoint.analysis.column_refs import calculated_cycle, formula_column_refs
from dbml_sharepoint.analysis.findings import Finding, FindingCode, Location, Section
from dbml_sharepoint.analysis.formula.functions import SUPPORTED, VOLATILE
from dbml_sharepoint.analysis.formula.parse import parse_formula
from dbml_sharepoint.analysis.formula.syntax import (
    Binary,
    Call,
    ColumnKind,
    Expr,
    FormulaSyntaxError,
    Neg,
    Num,
    Percent,
    Ref,
    Text,
)

# Supported names the date translation (not yet written) will take over; the parity-case test
# tolerates exactly these.
PENDING_DATES: frozenset[str] = frozenset({"DATE", "YEAR", "MONTH", "DAY"})

_SENTINEL = chr(0xE000)
# A choice column reads as text; its listed values do not matter to a formula.
_KIND = {"text": "text", "choice": "text", "number": "number", "date": "date"}


class FormulaRefusal(Exception):  # noqa: N818 -- named for the finding it becomes, not an error type
    """A formula that cannot be translated; `code` is the finding it becomes."""

    def __init__(self, code: FindingCode, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail

    def finding(self, entity: str, column: str, formula: str) -> Finding:
        return Finding(
            self.code,
            f"{entity}.{column}: the header formula {formula!r} {self.detail}.",
            location=Location(Section.FORM_FORMATTING, entity=entity, column=column),
        )


@dataclass(frozen=True, slots=True)
class Translation:
    expression: str
    result: Literal["text", "number", "date"]


@dataclass(frozen=True, slots=True)
class TranslationContext:
    formulas: Mapping[str, str]
    kinds: Mapping[str, ColumnKind]
    result_types: Mapping[str, str]
    choices: Mapping[str, tuple[str, ...]]
    zone: str


@dataclass(frozen=True, slots=True)
class _Tr:
    code: str
    kind: Literal["text", "number", "bool"]
    # A number column read directly: Learn does not say if a blank is null or 0.
    bare: bool = False


def _refuse(code: FindingCode, detail: str) -> NoReturn:
    raise FormulaRefusal(code, detail)


def _unsupported(name: str, why: str) -> NoReturn:
    _refuse(FindingCode.FORM_FORMULA_FUNCTION_UNSUPPORTED, f"uses {name}, {why}")


def _translate_date_call(name: str) -> NoReturn:
    _unsupported(name, "which a header cannot reproduce")


def _q(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"


def _lit(value: float) -> str:
    return str(int(value)) if value == int(value) else f"{Decimal(repr(value)):f}"


def _num(tr: _Tr, what: str) -> str:
    if tr.kind != "number":
        _refuse(FindingCode.FORM_FORMULA_UNPARSEABLE, f"uses {what} on a {tr.kind} value")
    # Number() is on the Learn page; it turns a null or empty blank into 0, which the measured
    # blank-number rule (counts as 0 in arithmetic and comparison) needs.
    return f"Number({tr.code})" if tr.bare else tr.code


def _cond(tr: _Tr) -> str:
    if tr.kind == "bool":
        return tr.code
    if tr.kind == "number":
        return f"({_num(tr, 'a condition')} != 0)"
    return _refuse(FindingCode.FORM_FORMULA_UNPARSEABLE, "uses a text value as a condition")


def _text_of(node: Expr, tr: _Tr, name: str) -> str:
    if tr.kind == "text":
        return tr.code
    # A computed number prints with SharePoint's 15 significant digits, which toString does not.
    if isinstance(node, Num):
        return _q(f"{node.value:.15g}")
    return _unsupported(
        name, "which joins a number as text and a header cannot print it the same way"
    )


def _whole(node: Expr, name: str, minimum: int) -> int:
    if not isinstance(node, Num) or node.value != int(node.value) or node.value < minimum:
        _unsupported(name, "with a count that is not a whole-number literal")
    return int(node.value)


def _text_length(text: str) -> str:
    # indexOf on the text plus a marker is the length workaround on the Learn page (indexOf);
    # shortcut: exact only while the text holds no U+E000, upgrade when a column may.
    return f"indexOf({text} + {_q(_SENTINEL)}, {_q(_SENTINEL)})"


def _text_ref(name: str) -> str:
    # length() is 0 for a blank and 1 for any other text (Learn: length), so a blank reads as ''.
    return f"if(length([${name}]) == 0, '', [${name}])"


class _Translator:
    def __init__(self, ctx: TranslationContext) -> None:
        self.ctx = ctx

    def column(self, name: str, stack: tuple[str, ...]) -> _Tr:
        try:
            expr = parse_formula(self.ctx.formulas[name])
        except FormulaSyntaxError as error:
            return _refuse(FindingCode.FORM_FORMULA_UNPARSEABLE, f"does not parse: {error}")
        return self.go(expr, (*stack, name))

    def go(self, node: Expr, stack: tuple[str, ...]) -> _Tr:
        match node:
            case Num(value=value):
                return _Tr(_lit(value), "number")
            case Text(value=value):
                return _Tr(_q(value), "text")
            case Ref(name=name):
                return self.ref(name, stack)
            case Neg(operand=operand):
                return _Tr(f"(0 - {_num(self.go(operand, stack), 'a minus sign')})", "number")
            case Percent(operand=operand):
                return _Tr(f"({_num(self.go(operand, stack), '%')} / 100)", "number")
            case Binary(op=op, left=left, right=right):
                return self.binary(op, left, right, stack)
            case Call(name=name, args=args):
                return self.call(name, args, stack)
        raise AssertionError(node)

    def stored_kind(self, name: str) -> str:
        return _KIND.get(self.ctx.kinds.get(name, ""), "")

    def ref(self, name: str, stack: tuple[str, ...]) -> _Tr:
        if name in self.ctx.formulas:
            if name in stack:
                _refuse(
                    FindingCode.FORM_FORMULA_UNPARSEABLE,
                    f"refers to [{name}], which refers back to it",
                )
            return self.column(name, stack)
        kind = self.stored_kind(name)
        if kind == "text":
            return _Tr(_text_ref(name), "text")
        if kind == "number":
            return _Tr(f"[${name}]", "number", bare=True)
        if kind == "date":
            _translate_date_call(f"the date column [{name}]")
        return _refuse(
            FindingCode.FORM_FORMULA_COLUMN_UNSUPPORTED,
            f"reads [{name}], which is not a text, number, date or choice column",
        )

    def binary(self, op: str, left: Expr, right: Expr, stack: tuple[str, ...]) -> _Tr:
        a, b = self.go(left, stack), self.go(right, stack)
        if op == "&":
            return _Tr(f"({_text_of(left, a, '&')} + {_text_of(right, b, '&')})", "text")
        if op in ("=", "<>", "<", ">", "<=", ">="):
            return self.compare(op, a, b)
        x, y = _num(a, op), _num(b, op)
        # pow and the arithmetic signs are on the Learn page (Binary operators).
        return _Tr(f"pow({x}, {y})" if op == "^" else f"({x} {op} {y})", "number")

    def compare(self, op: str, a: _Tr, b: _Tr) -> _Tr:
        js = {"=": "==", "<>": "!="}.get(op, op)
        if a.kind == b.kind == "text":
            if op not in ("=", "<>"):
                _unsupported(op, "which orders text and a header cannot match the column's order")
            # Text equality ignores case (measured); toLowerCase is on the Learn page.
            return _Tr(f"(toLowerCase({a.code}) {js} toLowerCase({b.code}))", "bool")
        return _Tr(f"({_num(a, op)} {js} {_num(b, op)})", "bool")

    def call(self, name: str, args: tuple[Expr, ...], stack: tuple[str, ...]) -> _Tr:
        if name in VOLATILE:
            _refuse(
                FindingCode.FORM_FORMULA_VOLATILE,
                f"calls {name}, whose value changes with no column changing",
            )
        if name not in SUPPORTED:
            _unsupported(name, "which has no formatting equivalent")
        low, high = SUPPORTED[name]
        if len(args) < low or (high is not None and len(args) > high):
            _refuse(FindingCode.FORM_FORMULA_UNPARSEABLE, f"gives {name} {len(args)} arguments")
        if name in PENDING_DATES:
            _translate_date_call(name)
        if name == "ISBLANK":
            return self.isblank(args[0])
        vals = [self.go(arg, stack) for arg in args]
        return self.apply(name, args, vals)

    def isblank(self, arg: Expr) -> _Tr:
        if (
            not isinstance(arg, Ref)
            or arg.name in self.ctx.formulas
            or self.stored_kind(arg.name) != "text"
        ):
            _unsupported("ISBLANK", "which a header can test only on a text or choice column")
        return _Tr(f"(length([${arg.name}]) == 0)", "bool")

    def apply(self, name: str, args: tuple[Expr, ...], vals: list[_Tr]) -> _Tr:
        match name:
            case "IF" | "CHOOSE":
                return self.branch(name, vals)
            case "AND" | "OR":
                joiner = " && " if name == "AND" else " || "
                return _Tr("(" + joiner.join(_cond(v) for v in vals) + ")", "bool")
            case "NOT":
                # The Learn page lists no unary not, so negate with a conditional on constants.
                return _Tr(f"if({_cond(vals[0])}, 0 == 1, 0 == 0)", "bool")
            case "MIN" | "MAX":
                return _Tr(self.extreme(name, [_num(v, name) for v in vals]), "number")
            case "ABS" | "INT":
                fn = "abs" if name == "ABS" else "floor"  # Learn: abs, floor
                return _Tr(f"{fn}({_num(vals[0], name)})", "number")
            case "ROUND":
                return self.round(args, vals)
            case "CONCATENATE":
                parts = [_text_of(a, v, name) for a, v in zip(args, vals, strict=True)]
                return _Tr("(" + " + ".join(parts) + ")", "text")
        return self.text_function(name, args, vals)

    def branch(self, name: str, vals: list[_Tr]) -> _Tr:
        if name == "IF":
            if len(vals) < 3:
                _unsupported("IF", "without an else value, which is not measured")
            yes, no = vals[1], vals[2]
            self.same_kind(name, [yes, no])
            return _Tr(f"if({_cond(vals[0])}, {self.value(yes)}, {self.value(no)})", yes.kind)
        index = _num(vals[0], name)
        options = vals[1:]
        self.same_kind(name, options)
        # Assumed: an out-of-range index is a column error (hidden); the last value is the default.
        code = self.value(options[-1])
        for i in range(len(options) - 1, 0, -1):
            code = f"if({index} == {i}, {self.value(options[i - 1])}, {code})"
        return _Tr(code, options[0].kind)

    @staticmethod
    def value(tr: _Tr) -> str:
        if tr.bare:
            _refuse(
                FindingCode.FORM_FORMULA_COLUMN_UNSUPPORTED,
                "returns a number column directly, and a header cannot tell its blank from 0",
            )
        if tr.kind == "bool":
            _refuse(FindingCode.FORM_FORMULA_RESULT_UNSUPPORTED, "returns a yes/no value")
        return tr.code

    @staticmethod
    def same_kind(name: str, vals: list[_Tr]) -> None:
        if len({v.kind for v in vals}) > 1:
            _refuse(FindingCode.FORM_FORMULA_UNPARSEABLE, f"gives {name} values of different types")

    @staticmethod
    def extreme(name: str, parts: list[str]) -> str:
        sign = "<" if name == "MIN" else ">"
        code = parts[0]
        for part in parts[1:]:
            code = f"if({code} {sign} {part}, {code}, {part})"
        return code

    @staticmethod
    def round(args: tuple[Expr, ...], vals: list[_Tr]) -> _Tr:
        # Whole places only: fractional places differ in floating point (1.005).
        if _whole(args[1], "ROUND", 0) != 0:
            _unsupported(
                "ROUND", "with places other than 0, which a header cannot round the same way"
            )
        x = _num(vals[0], "ROUND")
        # Half away from zero, built from floor (Learn: floor) because the page lists no round.
        return _Tr(f"if({x} < 0, 0 - floor(0 - {x} + 0.5), floor({x} + 0.5))", "number")

    @staticmethod
    def text_function(name: str, args: tuple[Expr, ...], vals: list[_Tr]) -> _Tr:
        s = vals[0]
        if s.kind != "text":
            _refuse(FindingCode.FORM_FORMULA_UNPARSEABLE, f"gives {name} a {s.kind} value")
        match name:
            case "LOWER":
                return _Tr(f"toLowerCase({s.code})", "text")  # Learn: toLowerCase
            case "UPPER":
                return _Tr(f"toUpperCase({s.code})", "text")  # Learn: toUpperCase
            case "LEN":
                return _Tr(_text_length(s.code), "number")
            case "LEFT":
                count = _whole(args[1], name, 0) if len(args) > 1 else 1
                return _Tr(f"substring({s.code}, 0, {count})", "text")  # Learn: substring
            case "RIGHT":
                count = _whole(args[1], name, 0) if len(args) > 1 else 1
                size = _text_length(s.code)
                return _Tr(f"substring({s.code}, {size} - {count}, {size})", "text")
        start = _whole(args[1], name, 1)
        length = _whole(args[2], name, 0)
        return _Tr(f"substring({s.code}, {start - 1}, {start - 1 + length})", "text")


def translate_column(column: str, ctx: TranslationContext) -> Translation:
    """The formatting expression a header evaluates for calculated column `column`."""
    declared = ctx.result_types.get(column)
    if declared not in ("text", "number", "date") or column not in ctx.formulas:
        _refuse(
            FindingCode.FORM_FORMULA_RESULT_UNSUPPORTED,
            f"has the result type {declared!r}, which a header cannot show",
        )
    reachable: set[str] = set()
    todo = [column]
    while todo:
        name = todo.pop()
        if name in ctx.formulas and name not in reachable:
            reachable.add(name)
            todo += formula_column_refs(ctx.formulas[name])
    if members := calculated_cycle({n: ctx.formulas[n] for n in reachable}, reachable):
        _refuse(
            FindingCode.FORM_FORMULA_UNPARSEABLE, f"is part of a circular reference among {members}"
        )
    tr = _Translator(ctx).column(column, ())
    code = _Translator.value(tr)
    if tr.kind != declared:
        _refuse(
            FindingCode.FORM_FORMULA_RESULT_UNSUPPORTED,
            f"returns a {tr.kind} but the column is {declared}",
        )
    return Translation("=" + code, declared)
