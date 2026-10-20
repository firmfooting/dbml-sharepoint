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
from dbml_sharepoint.analysis.findings import FindingCode
from dbml_sharepoint.analysis.formula.functions import SUPPORTED, VOLATILE
from dbml_sharepoint.analysis.formula.parse import parse_formula
from dbml_sharepoint.analysis.formula.refusal import FormulaRefusal
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
from dbml_sharepoint.analysis.formula.zone import (
    ZoneRule,
    day_of_instant,
    days_of,
    midnight_ms,
    out_of_span_day,
    out_of_span_instant,
    parts_of,
    zone_rule,
)

# Date columns a formula may read: never blank, and Learn documents a date field as a date that
# Date() and Number() accept. Any other date column is refused, as Learn leaves a blank one open.
_SYSTEM_DATES = frozenset({"Created", "Modified"})
# An expression longer than this is refused: nested date arithmetic repeats its operands.
_MAX_EXPRESSION = 250_000

# Refused with the reason, not merely absent from SUPPORTED.
_NO_EQUIVALENT = {
    "TRIM": "which also collapses inner runs of spaces, and formatting has no trim operator",
    "LEN": "and the formatting reference documents no text-length operator",
    "RIGHT": "and the formatting reference documents no text-length operator to count from the end",
}
# A choice column reads as text; its listed values do not matter to a formula.
_KIND = {"text": "text", "choice": "text", "number": "number", "date": "date"}


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
    """A translated value. A "date" is a day number on the site's calendar, an "instant" is epoch
    milliseconds (a system date column); `whole` is True when the value is provably an integer."""

    code: str
    kind: Literal["text", "number", "bool", "date", "instant"]
    whole: bool = False


def _refuse(code: FindingCode, detail: str) -> NoReturn:
    raise FormulaRefusal(code, detail)


def _unsupported(name: str, why: str) -> NoReturn:
    _refuse(FindingCode.FORM_FORMULA_FUNCTION_UNSUPPORTED, f"uses {name}, {why}")


def _q(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"


def _lit(value: float) -> str:
    return str(int(value)) if value == int(value) else f"{Decimal(repr(value)):f}"


def _num(tr: _Tr, what: str) -> str:
    if tr.kind != "number":
        _unsupported(what, f"which cannot take a {tr.kind} value")
    return tr.code


def _cond(tr: _Tr) -> str:
    if tr.kind == "bool":
        return tr.code
    if tr.kind == "number":
        return f"({_num(tr, 'a condition')} != 0)"
    return _refuse(FindingCode.FORM_FORMULA_UNPARSEABLE, f"uses a {tr.kind} value as a condition")


def _text_of(node: Expr, tr: _Tr, name: str) -> str:
    if tr.kind == "text":
        return tr.code
    # A computed number prints with SharePoint's 15 significant digits, which toString does not.
    if isinstance(node, Num):
        return _q(f"{node.value:.15g}")
    return _unsupported(
        name, "which joins a number as text and a header cannot print it the same way"
    )


def _whole_values(node: Expr) -> set[float] | None:
    """Every value of a whole-number literal or an IF over such; None for anything else."""
    if isinstance(node, Num):
        return {node.value} if node.value == int(node.value) else None
    if isinstance(node, Call) and node.name == "IF" and len(node.args) == 3:
        branches = (_whole_values(node.args[1]), _whole_values(node.args[2]))
        if branches[0] is not None and branches[1] is not None:
            return branches[0] | branches[1]
    return None


def _whole(node: Expr, name: str, minimum: int) -> int:
    if not isinstance(node, Num) or node.value != int(node.value) or node.value < minimum:
        _unsupported(name, "with a count that is not a whole-number literal")
    return int(node.value)


class _Translator:
    def __init__(self, ctx: TranslationContext) -> None:
        self.ctx = ctx
        # Conditions under which a date is outside the verified years; they blank the whole result.
        self.out_of_span: list[str] = []
        self._rule: ZoneRule | None = None

    @property
    def rule(self) -> ZoneRule:
        if self._rule is None:
            self._rule = zone_rule(self.ctx.zone)
        return self._rule

    def day(self, tr: _Tr) -> str:
        """The day number of a date, or of an instant read on the site's calendar."""
        if tr.kind == "date":
            return tr.code
        self.out_of_span.append(out_of_span_instant(tr.code, self.rule))
        return day_of_instant(tr.code, self.rule)

    def span_checked(self, days: str) -> str:
        self.out_of_span.append(out_of_span_day(days, self.rule))
        return days

    def column(self, name: str, stack: tuple[str, ...]) -> _Tr:
        try:
            expr = parse_formula(self.ctx.formulas[name])
        except FormulaSyntaxError as error:
            return _refuse(FindingCode.FORM_FORMULA_UNPARSEABLE, f"does not parse: {error}")
        return self.go(expr, (*stack, name))

    def go(self, node: Expr, stack: tuple[str, ...]) -> _Tr:
        tr = self.node(node, stack)
        if len(tr.code) > _MAX_EXPRESSION:  # stop before nested dates repeat themselves further
            _unsupported("date arithmetic", "nested so deeply that its expression is too large")
        return tr

    def node(self, node: Expr, stack: tuple[str, ...]) -> _Tr:
        match node:
            case Num(value=value):
                return _Tr(_lit(value), "number", whole=value == int(value))
            case Text(value=value):
                return _Tr(_q(value), "text")
            case Ref(name=name):
                return self.ref(name, stack)
            case Neg(operand=operand):
                inner = self.go(operand, stack)
                return _Tr(f"(0 - {_num(inner, 'a minus sign')})", "number", inner.whole)
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
            # A blank text field reads as '': Learn's own blank test on one (the default file
            # hover card sample in the formatting syntax reference) is `[$Field] == ''`.
            return _Tr(f"[${name}]", "text")
        if kind == "number":
            # Learn never says what a blank number field is, so a header cannot match 0 or blank.
            _refuse(
                FindingCode.FORM_FORMULA_COLUMN_UNSUPPORTED,
                f"reads the number column [{name}], whose blank value Learn does not document",
            )
        if kind == "date":
            if name in _SYSTEM_DATES:
                # Learn: a Date/Time field is a date; Number(Date(..)) is milliseconds since 1970.
                return _Tr(f"Number(Date([${name}]))", "instant")
            _refuse(
                FindingCode.FORM_FORMULA_COLUMN_UNSUPPORTED,
                f"reads the date column [{name}], whose blank value Learn does not document",
            )
        return _refuse(
            FindingCode.FORM_FORMULA_COLUMN_UNSUPPORTED,
            f"reads [{name}], which is not a text, number, date or choice column",
        )

    def binary(self, op: str, left: Expr, right: Expr, stack: tuple[str, ...]) -> _Tr:
        a, b = self.go(left, stack), self.go(right, stack)
        if op in ("+", "-") and {a.kind, b.kind} & {"date", "instant"}:
            return self.date_sum(op, a, b)
        if op == "&":
            return _Tr(f"({_text_of(left, a, '&')} + {_text_of(right, b, '&')})", "text")
        if op in ("=", "<>", "<", ">", "<=", ">="):
            return self.compare(op, a, b)
        x, y = _num(a, op), _num(b, op)
        # pow and the arithmetic signs are on the Learn page (Binary operators).
        return _Tr(
            f"pow({x}, {y})" if op == "^" else f"({x} {op} {y})",
            "number",
            a.whole and b.whole and op in ("+", "-", "*"),
        )

    def date_sum(self, op: str, a: _Tr, b: _Tr) -> _Tr:
        """Date plus or minus whole days, or the difference of two dates in days."""
        dates = (a.kind == "date", b.kind == "date")
        if all(dates) and op == "-":
            return _Tr(f"({a.code} - {b.code})", "number", whole=True)
        count, moment = (b, a) if a.kind in ("date", "instant") else (a, b)
        if (
            count.kind != "number"
            or not count.whole
            or (moment is b and op == "-")
            or moment.kind == "bool"
        ):
            _unsupported(op, "which a header reproduces only for a date and a whole number of days")
        return _Tr(f"({self.day(moment)} {op} {count.code})", "date")

    def compare(self, op: str, a: _Tr, b: _Tr) -> _Tr:
        js = {"=": "==", "<>": "!="}.get(op, op)
        if a.kind == b.kind == "date":
            return _Tr(f"({a.code} {js} {b.code})", "bool")
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
        if name in _NO_EQUIVALENT:
            _unsupported(name, _NO_EQUIVALENT[name])
        if name not in SUPPORTED:
            _unsupported(name, "which has no formatting equivalent")
        low, high = SUPPORTED[name]
        if len(args) < low or (high is not None and len(args) > high):
            _refuse(FindingCode.FORM_FORMULA_UNPARSEABLE, f"gives {name} {len(args)} arguments")
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
        return _Tr(f"([${arg.name}] == '')", "bool")

    def apply(self, name: str, args: tuple[Expr, ...], vals: list[_Tr]) -> _Tr:
        match name:
            case "IF" | "CHOOSE":
                return self.branch(name, args, vals)
            case "DATE" | "YEAR" | "MONTH" | "DAY":
                return self.date_call(name, vals)
            case "AND" | "OR":
                joiner = " && " if name == "AND" else " || "
                return _Tr("(" + joiner.join(_cond(v) for v in vals) + ")", "bool")
            case "NOT":
                # The Learn page lists no unary not, so negate with a conditional on constants.
                return _Tr(f"if({_cond(vals[0])}, 0 == 1, 0 == 0)", "bool")
            case "MIN" | "MAX":
                parts = [_num(v, name) for v in vals]
                return _Tr(self.extreme(name, parts), "number", all(v.whole for v in vals))
            case "ABS" | "INT":
                fn = "abs" if name == "ABS" else "floor"  # Learn: abs, floor
                return _Tr(f"{fn}({_num(vals[0], name)})", "number", name == "INT" or vals[0].whole)
            case "ROUND":
                return self.round(args, vals)
            case "CONCATENATE":
                parts = [_text_of(a, v, name) for a, v in zip(args, vals, strict=True)]
                return _Tr("(" + " + ".join(parts) + ")", "text")
        return self.text_function(name, args, vals)

    def date_call(self, name: str, vals: list[_Tr]) -> _Tr:
        if name == "DATE":
            if not all(v.kind == "number" and v.whole for v in vals):
                _unsupported(name, "with an argument that is not provably a whole number")
            return _Tr(days_of(*(v.code for v in vals)), "date")
        moment = vals[0]
        if moment.kind not in ("date", "instant"):
            _unsupported(name, f"of a {moment.kind} value")
        days = self.day(moment)
        if moment.kind == "date":
            self.span_checked(days)
        year, month, day = parts_of(days)
        return _Tr({"YEAR": year, "MONTH": month, "DAY": day}[name], "number", whole=True)

    def branch(self, name: str, args: tuple[Expr, ...], vals: list[_Tr]) -> _Tr:
        if name == "IF":
            if len(vals) < 3:
                _unsupported("IF", "without an else value, which is not measured")
            yes, no = vals[1], vals[2]
            self.same_kind(name, [yes, no])
            return _Tr(
                f"if({_cond(vals[0])}, {self.value(yes)}, {self.value(no)})",
                yes.kind,
                yes.whole and no.whole,
            )
        index = _num(vals[0], name)
        options = vals[1:]
        self.same_kind(name, options)
        reach = _whole_values(args[0])
        if reach is None or not reach <= set(range(1, len(options) + 1)):
            _unsupported(name, "with an index not provably a whole number in range")
        # The index is proven in range, so the last value is simply the else.
        code = self.value(options[-1])
        for i in range(len(options) - 1, 0, -1):
            code = f"if({index} == {i}, {self.value(options[i - 1])}, {code})"
        return _Tr(code, options[0].kind, all(o.whole for o in options))

    @staticmethod
    def value(tr: _Tr) -> str:
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
        return _Tr(f"if({x} < 0, 0 - floor(0 - {x} + 0.5), floor({x} + 0.5))", "number", True)

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
            case "LEFT":
                count = _whole(args[1], name, 0) if len(args) > 1 else 1
                return _Tr(f"substring({s.code}, 0, {count})", "text")  # Learn: substring
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
    translator = _Translator(ctx)
    tr = translator.column(column, ())
    if tr.kind == "instant":
        _refuse(
            FindingCode.FORM_FORMULA_RESULT_UNSUPPORTED,
            "returns a date with a time of day, which a header cannot show the same way",
        )
    if tr.kind == "date":
        days = translator.span_checked(tr.code)
        tr = _Tr(f"Date({midnight_ms(days, translator.rule)})", "date")
    code = _Translator.value(tr)
    if tr.kind != declared:
        _refuse(
            FindingCode.FORM_FORMULA_RESULT_UNSUPPORTED,
            f"returns a {tr.kind} but the column is {declared}",
        )
    if translator.out_of_span:
        # One blank for the whole result: a date outside the verified years has no exact offset.
        code = f"if({' || '.join(dict.fromkeys(translator.out_of_span))}, '', {code})"
    if len(code) > _MAX_EXPRESSION:
        _unsupported("date arithmetic", "nested so deeply that its expression is too large")
    return Translation("=" + code, declared)
