"""Translate a calculated column's formula into a column-formatting expression.

The expression is what a form header evaluates in place of the column, because a header reads a
calculated column as blank. Anything the formatting language cannot reproduce exactly is refused
by name; a header that could differ from its column on one row is a failed build.

Formatting functions used here are listed on the formatting syntax reference (Microsoft Learn,
https://learn.microsoft.com/en-us/sharepoint/dev/declarative-customization/formatting-syntax-reference),
each cited where it is emitted.

A date inside a translation is a day number on the site's calendar. A date column is read through
its epoch milliseconds, `Number([$D])`, never through the browser-zone date parts (getDate and
the like), so the day does not depend on the viewer's zone.
"""

import dataclasses
import math
import operator
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Literal, NoReturn

from dbml_sharepoint.analysis.column_refs import calculated_cycle, formula_column_refs
from dbml_sharepoint.analysis.findings import FindingCode
from dbml_sharepoint.analysis.formatter_values import quoted
from dbml_sharepoint.analysis.formula.civil import (
    END_DAY,
    FIRST_DAY,
    days_of,
    from_day_number,
    parts_of,
    to_day_number,
)
from dbml_sharepoint.analysis.formula.functions import SUPPORTED, VOLATILE
from dbml_sharepoint.analysis.formula.parse import parse_formula
from dbml_sharepoint.analysis.formula.refusal import FormulaRefusal, too_large
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
from dbml_sharepoint.analysis.formula.tables import tabulate as build_table
from dbml_sharepoint.analysis.formula.zone import out_of_span_instant, site_day, zone_rule
from dbml_sharepoint.analysis.limits import FORM_HEADER_MAX_CHARS

# These two never hold a blank, so a formula may read them without testing for one.
_SYSTEM_MOMENTS = frozenset({"Created", "Modified"})
NEVER = "0 == 1"
ALWAYS = "0 == 0"
# Enumeration bound for the values a number or date can take, so a date's range can be proven.
_ARITHMETIC = {"+": operator.add, "-": operator.sub, "*": operator.mul}
_MAX_VALUES = 4096  # a work bound on enumeration, not a platform fact

# Refused with the reason, not merely absent from SUPPORTED.
_NO_EQUIVALENT = {
    "TRIM": "which also collapses inner runs of spaces, and formatting has no trim operator",
    "LEN": "and the formatting reference documents no text-length operator",
    "RIGHT": "and the formatting reference documents no text-length operator to count from the end",
}
_NO_QUOTE = "and no escape for one inside an expression is measured"
# A choice column reads as text; its listed values do not matter to a formula.
_CHOICE_KINDS = frozenset({"choice"})
_KIND = {"text": "text", "choice": "text", "number": "number", "date": "date"}


@dataclass(frozen=True, slots=True)
class Translation:
    """`expression` is the whole value. A date's value is its day number, `day`, or '' while `blank`
    holds (empty when it never does); the two parts are kept so a header can show the day."""

    expression: str
    result: Literal["text", "number", "date"]
    day: str = ""
    blank: str = ""


@dataclass(frozen=True, slots=True)
class TranslationContext:
    formulas: Mapping[str, str]
    kinds: Mapping[str, ColumnKind]
    result_types: Mapping[str, str]
    choices: Mapping[str, tuple[str, ...]]
    zone: str
    # Date columns that hold a time of day (date and time columns); Created and Modified always do.
    moments: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class _Tr:
    """A translated value. A "date" is a day number on a fixed calendar. `values` is every value a
    number or date can take (None when unknown), which is how a date's range is proven; a value
    of unknown range is checked when the formula runs instead. `moment` marks a date that came
    from a date-and-time column, whose time of day the day number drops. `instant` names the stored
    date column a value was read from: a calculated column sees such a column as a fractional
    serial of its instant, so comparing or subtracting it is not whole days."""

    code: str
    kind: Literal["text", "number", "bool", "date"]
    values: frozenset[float] | None = None
    integral: bool = False  # a whole number by construction, when `values` is unknown
    moment: bool = False
    instant: str = ""
    truth: bool | None = None  # the value of a condition built from constants alone

    @property
    def whole(self) -> bool:
        return self.integral or (self.values is not None and all(v == int(v) for v in self.values))


def _combine(a: _Tr, b: _Tr, fn: Callable[[float, float], float]) -> frozenset[float] | None:
    if a.values is None or b.values is None or len(a.values) * len(b.values) > _MAX_VALUES:
        return None
    return frozenset(fn(x, y) for x in a.values for y in b.values)


def _union(*trs: _Tr) -> frozenset[float] | None:
    if any(t.values is None for t in trs):
        return None
    return frozenset().union(*(t.values or frozenset() for t in trs))


def _mapped(tr: _Tr, fn: Callable[[float], float]) -> frozenset[float] | None:
    return None if tr.values is None else frozenset(fn(v) for v in tr.values)


def _refuse(code: FindingCode, detail: str) -> NoReturn:
    raise FormulaRefusal(code, detail)


def _unsupported(name: str, why: str) -> NoReturn:
    _refuse(FindingCode.FORM_FORMULA_FUNCTION_UNSUPPORTED, f"uses {name}, {why}")


def _lit(value: float) -> str:
    return str(int(value)) if value == int(value) else f"{Decimal(repr(value)):f}"


def _power_is_safe(base: _Tr, exponent: _Tr) -> bool:
    """Every base and exponent pair is known and none is zero to a non-positive power or a
    negative base to a fractional one, which are column errors (zero to zero is measured)."""
    if base.values is None or exponent.values is None:
        return False
    return not any(
        (x == 0 and y <= 0) or (x < 0 and y != int(y)) for x in base.values for y in exponent.values
    )


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
        text = f"{node.value:.15g}"
        # Scientific forms (1e+18, 1e-05) are not known to match how the column prints them.
        if abs(node.value) < 1e15 and "e" not in text:
            return quoted(text)
    return _unsupported(
        name, "which joins a number as text and a header cannot print it the same way"
    )


def _is_empty(node: Expr) -> bool:
    return isinstance(node, Text) and node.value == ""


def _whole_values(node: Expr) -> set[float] | None:
    """Every value of a whole-number literal, or an IF or +, - and * over such; else None."""
    if isinstance(node, Num):
        return {node.value} if node.value == int(node.value) else None
    if isinstance(node, Binary) and node.op in _ARITHMETIC:
        left, right = _whole_values(node.left), _whole_values(node.right)
        if left is None or right is None or len(left) * len(right) > _MAX_VALUES:
            return None
        return {_ARITHMETIC[node.op](x, y) for x in left for y in right}
    if isinstance(node, Call) and node.name == "IF" and len(node.args) == 3:
        branches = (_whole_values(node.args[1]), _whole_values(node.args[2]))
        if branches[0] is not None and branches[1] is not None:
            return branches[0] | branches[1]
    return None


def _calendar_day(year: int, month: int, day: int) -> tuple[int, int]:
    """Day numbers of the month's first day and of DATE(year, month, day), with overflow carried."""
    if year < 1:
        _unsupported("DATE", "with a year before 1")
    try:
        first = date(year + (month - 1) // 12, (month - 1) % 12 + 1, 1)
        return to_day_number(first), to_day_number(first + timedelta(days=day - 1))
    except (ValueError, OverflowError):
        _unsupported("DATE", "on a date outside years 1 to 9999")


def _any(conditions: list[str]) -> str:
    return " || ".join(dict.fromkeys(conditions))


def _outside_days(days: str) -> str:
    # The quotient is 0 only inside [FIRST_DAY, END_DAY).
    return f"(floor((({days}) + {-FIRST_DAY}) / {END_DAY - FIRST_DAY}) != 0)"


def _filled(cond: Expr) -> tuple[frozenset[str], frozenset[str]]:
    """Columns an ISBLANK test proves filled when `cond` is true, and when it is false."""
    none: frozenset[str] = frozenset()
    if not isinstance(cond, Call):
        return none, none
    if cond.name == "ISBLANK" and isinstance(cond.args[0], Ref):
        return none, frozenset({cond.args[0].name})
    parts = [_filled(arg) for arg in cond.args]
    if cond.name == "NOT" and len(parts) == 1:
        return parts[0][1], parts[0][0]
    if cond.name == "AND":
        return frozenset().union(*(p[0] for p in parts)), none
    if cond.name == "OR":
        return none, frozenset().union(*(p[1] for p in parts))
    return none, none


def _in_range(name: str, days: set[float]) -> frozenset[float]:
    """The dates, when every one is where the calendar arithmetic is exact."""
    if not days or len(days) > _MAX_VALUES or not all(FIRST_DAY <= d < END_DAY for d in days):
        _unsupported(name, "on a date not known to fall between March 1904 and February 2100")
    return frozenset(days)


def _whole(node: Expr, name: str, minimum: int) -> int:
    if not isinstance(node, Num) or node.value != int(node.value) or node.value < minimum:
        _unsupported(name, "with a count that is not a whole-number literal")
    return int(node.value)


class _Translator:
    def __init__(self, ctx: TranslationContext) -> None:
        self.ctx = ctx
        # Conditions under which the value on the current path is outside what the arithmetic
        # proves; an IF or CHOOSE collects each branch's own, so an untaken branch cannot blank.
        self.fails: list[str] = []
        self.filled: frozenset[str] = frozenset()  # date columns known filled on this path

    def column(self, name: str, stack: tuple[str, ...]) -> _Tr:
        try:
            expr = parse_formula(self.ctx.formulas[name])
        except FormulaSyntaxError as error:
            return _refuse(FindingCode.FORM_FORMULA_UNPARSEABLE, f"does not parse: {error}")
        if not stack and (guarded := self.blank_guarded(expr, (name,))) is not None:
            return guarded
        return self.go(expr, (*stack, name))

    def blank_guarded(self, expr: Expr, stack: tuple[str, ...]) -> _Tr | None:
        """IF(test, "", date) or IF(test, date, ""): the date, blank where the formula gives ''.

        Only as the whole formula, so a blank never feeds further arithmetic.
        Assumes (unmeasured) that a computed date returning "" displays blank.
        """
        if not (isinstance(expr, Call) and expr.name == "IF" and len(expr.args) == 3):
            return None
        test, yes, no = expr.args
        empty_yes, empty_no = (isinstance(a, Text) and a.value == "" for a in (yes, no))
        if empty_yes == empty_no:
            return None
        if_true, if_false = _filled(test)
        kept, filled = (no, if_false) if empty_yes else (yes, if_true)
        condition = self.go(test, stack)
        found, fail = self.scoped(kept, stack, self.filled | filled)
        if found.kind != "date":
            return None
        blank = _cond(condition) if empty_yes else f"if({_cond(condition)}, {NEVER}, {ALWAYS})"
        self.fails.append(f"if({blank}, {ALWAYS}, {fail or NEVER})")
        return found

    def go(self, node: Expr, stack: tuple[str, ...]) -> _Tr:
        tr = self.node(node, stack)
        if len(tr.code) > FORM_HEADER_MAX_CHARS:  # nested dates repeat their operands
            raise too_large(len(tr.code))
        return tr

    def node(self, node: Expr, stack: tuple[str, ...]) -> _Tr:
        match node:
            case Num(value=value):
                return _Tr(_lit(value), "number", frozenset({value}))
            case Text(value=value):
                if "'" in value:
                    _unsupported("a text with a single quote", _NO_QUOTE)
                return _Tr(quoted(value), "text")
            case Ref(name=name):
                return self.ref(name, stack)
            case Neg(operand=operand):
                inner = self.go(operand, stack)
                values = _mapped(inner, lambda v: -v)
                return _Tr(f"(0 - {_num(inner, 'a minus sign')})", "number", values, inner.whole)
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
            return self.date_field(name)
        return _refuse(
            FindingCode.FORM_FORMULA_COLUMN_UNSUPPORTED,
            f"reads [{name}], which is not a text, number, date or choice column",
        )

    def date_field(self, name: str) -> _Tr:
        system = name in _SYSTEM_MOMENTS
        if not system and name not in self.filled:
            # A blank date reads as 0 and the formatter has no test for it but toString == ''.
            _refuse(
                FindingCode.FORM_FORMULA_COLUMN_UNSUPPORTED,
                f"reads the date column [{name}] where it can be blank, which a header "
                "reproduces only in the branch of an ISBLANK test that excludes the blank",
            )
        ms = f"Number([${name}])"
        # Measured: every date column keeps the instant written, so its day is the site's day of it.
        rule = zone_rule(self.ctx.zone)
        if rule.daylight is not None:  # a fixed offset is exact for any instant
            self.fails.append(out_of_span_instant(ms, rule))
        return _Tr(
            site_day(ms, rule), "date", moment=system or name in self.ctx.moments, instant=name
        )

    def binary(self, op: str, left: Expr, right: Expr, stack: tuple[str, ...]) -> _Tr:
        a, b = self.go(left, stack), self.go(right, stack)
        if op in ("+", "-") and "date" in {a.kind, b.kind}:
            return self.date_sum(op, a, b)
        if op == "&":
            return _Tr(f"({_text_of(left, a, '&')} + {_text_of(right, b, '&')})", "text")
        if op in ("=", "<>", "<", ">", "<=", ">="):
            return self.compare(op, a, b)
        x, y = _num(a, op), _num(b, op)
        if op == "/" and (b.values is None or 0 in b.values):
            _unsupported(op, "with a divisor not provably nonzero, where the column is an error")
        if op == "^" and not _power_is_safe(a, b):
            _unsupported(op, "with a base and exponent not provably free of a column error")
        # pow and the arithmetic signs are on the Learn page (Binary operators).
        ops: dict[str, Callable[[float, float], float]] = {
            "+": lambda p, q: p + q,
            "-": lambda p, q: p - q,
            "*": lambda p, q: p * q,
        }
        values = _combine(a, b, ops[op]) if op in ops else None
        whole = op in ops and a.whole and b.whole
        return _Tr(
            f"pow({x}, {y})" if op == "^" else f"({x} {op} {y})", "number", values, whole
        )

    def date_sum(self, op: str, a: _Tr, b: _Tr) -> _Tr:
        """Date plus or minus whole days, or the difference of two dates in days."""
        sign = 1 if op == "+" else -1
        if a.kind == b.kind == "date" and op == "-":
            self.no_time_of_day(op, a, b)
            values = _combine(a, b, lambda p, q: p - q)
            return _Tr(f"({a.code} - {b.code})", "number", values, integral=True)
        moment, count = (a, b) if a.kind == "date" else (b, a)
        if count.kind != "number" or not count.whole or (moment is b and op == "-"):
            _unsupported(op, "which a header reproduces only for a date and a whole number of days")
        values = _combine(moment, count, lambda p, q: p + sign * q)
        # The day number drops the time of day, so a display is exact; a comparison is not.
        return _Tr(f"({moment.code} {op} {count.code})", "date", values, instant=moment.instant)

    @staticmethod
    def no_time_of_day(op: str, *dates: _Tr) -> None:
        if named := next((d.instant for d in dates if d.instant), ""):
            _unsupported(
                op,
                f"which compares or subtracts the date column [{named}] by its instant, and a "
                "calculated column sees that as a fraction of a day, not a whole one",
            )

    def compare(self, op: str, a: _Tr, b: _Tr) -> _Tr:
        js = {"=": "==", "<>": "!="}.get(op, op)
        if a.kind == b.kind == "date":
            self.no_time_of_day(op, a, b)
            return _Tr(f"({a.code} {js} {b.code})", "bool")
        if a.kind == b.kind == "text":
            if op not in ("=", "<>"):
                _unsupported(op, "which orders text and a header cannot match the column's order")
            # Text equality ignores case (measured); toLowerCase is on the Learn page.
            return _Tr(f"(toLowerCase({a.code}) {js} toLowerCase({b.code}))", "bool")
        _num(a, op), _num(b, op)
        if not (a.whole and b.whole):
            # Python or JavaScript floats can disagree with the column's arithmetic (0.1+0.2=0.3).
            _unsupported(op, "which compares numbers not known to be whole")
        truth = None
        if a.values is not None and b.values is not None and len(a.values) == len(b.values) == 1:
            (x,), (y,) = a.values, b.values
            order = {"=": x == y, "<>": x != y, "<": x < y, ">": x > y, "<=": x <= y, ">=": x >= y}
            truth = order[op]
        return _Tr(f"({_num(a, op)} {js} {_num(b, op)})", "bool", truth=truth)

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
        if name in ("IF", "CHOOSE"):
            return self.table(Call(name, args)) or self.branch(name, args, stack)
        vals = [self.go(arg, stack) for arg in args]
        return self.apply(name, args, vals)

    def table(self, node: Expr) -> _Tr | None:
        choices = frozenset(n for n, k in self.ctx.kinds.items() if k in _CHOICE_KINDS)
        found = build_table(node, self.ctx.formulas, choices, self.leaf)
        if found is None:
            return None
        code, leaves = found
        return self.joined(code, leaves)

    def leaf(self, expr: Expr) -> _Tr | None:
        """A table entry: the formula translated with no column left to read, or None."""
        sub = _Translator(self.ctx)
        try:
            tr = sub.go(expr, ())
        except FormulaRefusal:
            return None  # the plain translation refuses it, with the reason
        return tr if tr.kind in ("text", "number") and not sub.fails else None

    def isblank(self, arg: Expr) -> _Tr:
        if (
            isinstance(arg, Ref)
            and arg.name not in self.ctx.formulas
            and arg.name not in _SYSTEM_MOMENTS
        ):
            kind = self.stored_kind(arg.name)
            if kind == "text":
                return _Tr(f"([${arg.name}] == '')", "bool")
            if kind == "date":
                # Measured: a blank date field's toString is '' and no other value's is.
                return _Tr(f"(toString([${arg.name}]) == '')", "bool")
        return _unsupported("ISBLANK", "which a header can test only on a stored column")

    def apply(self, name: str, args: tuple[Expr, ...], vals: list[_Tr]) -> _Tr:
        match name:
            case "DATE" | "YEAR" | "MONTH" | "DAY":
                return self.date_call(name, vals)
            case "AND" | "OR":
                joiner = " && " if name == "AND" else " || "
                code = "(" + joiner.join(_cond(v) for v in vals) + ")"
                known = [v.truth for v in vals]
                if None in known:
                    return _Tr(code, "bool")
                return _Tr(code, "bool", truth=all(known) if name == "AND" else any(known))
            case "NOT":
                # The Learn page lists no unary not, so negate with a conditional on constants.
                code = f"if({_cond(vals[0])}, 0 == 1, 0 == 0)"
                return _Tr(code, "bool", truth=None if vals[0].truth is None else not vals[0].truth)
            case "MIN" | "MAX":
                parts = [_num(v, name) for v in vals]
                values = self.extremes(name, vals)
                return _Tr(self.extreme(name, parts), "number", values, all(v.whole for v in vals))
            case "ABS" | "INT":
                fn = "abs" if name == "ABS" else "floor"  # Learn: abs, floor
                shape = abs if name == "ABS" else math.floor
                if name == "INT" and not vals[0].whole:
                    _unsupported(name, "of a number not known to be whole, which is not measured")
                whole = name == "INT" or vals[0].whole
                code = f"{fn}({_num(vals[0], name)})"
                return _Tr(code, "number", _mapped(vals[0], shape), whole)
            case "ROUND":
                return self.round(args, vals)
            case "CONCATENATE":
                parts = [_text_of(a, v, name) for a, v in zip(args, vals, strict=True)]
                return _Tr("(" + " + ".join(parts) + ")", "text")
        return self.text_function(name, args, vals)

    def civil(self, name: str, moment: _Tr) -> None:
        """Make sure the date is where the calendar arithmetic is exact, now or when it runs."""
        if moment.values is None:
            self.fails.append(_outside_days(moment.code))
        else:
            _in_range(name, set(moment.values))

    def date_call(self, name: str, vals: list[_Tr]) -> _Tr:
        if name == "DATE":
            return self.date_of(vals)
        moment = vals[0]
        if moment.kind != "date":
            _unsupported(name, f"of a {moment.kind} value")
        self.civil(name, moment)
        year, month, day = parts_of(moment.code)
        pick: dict[str, Callable[[date], int]] = {
            "YEAR": lambda x: x.year,
            "MONTH": lambda x: x.month,
            "DAY": lambda x: x.day,
        }
        values = _mapped(moment, lambda v: pick[name](from_day_number(int(v))))
        return _Tr(
            {"YEAR": year, "MONTH": month, "DAY": day}[name], "number", values, integral=True
        )

    def date_of(self, vals: list[_Tr]) -> _Tr:
        if not all(v.kind == "number" and v.whole for v in vals):
            _unsupported("DATE", "with an argument not known to be a whole number")
        y, m, d = vals
        code = days_of(y.code, m.code, d.code)
        if y.values is None or m.values is None or d.values is None:
            # The month's first day matters too: the leap count is exact only inside the range.
            self.fails.append(_outside_days(days_of(y.code, m.code, "1")))
            self.fails.append(_outside_days(code))
            return _Tr(code, "date")
        if len(y.values) * len(m.values) * len(d.values) > _MAX_VALUES:
            _unsupported("DATE", "with too many possible arguments to check its dates")
        found = [
            _calendar_day(int(yy), int(mm), int(dd))
            for yy in y.values
            for mm in m.values
            for dd in d.values
        ]
        _in_range("DATE", {first for first, _ in found})
        return _Tr(code, "date", _in_range("DATE", {day for _, day in found}))

    def scoped(self, node: Expr, stack: tuple[str, ...], filled: frozenset[str]) -> tuple[_Tr, str]:
        """Translate a branch on its own path; its failure conditions come back, not collected."""
        outer, outer_filled = self.fails, self.filled
        mine: list[str] = []
        self.fails, self.filled = mine, filled
        try:
            return self.go(node, stack), _any(mine)
        finally:
            self.fails, self.filled = outer, outer_filled

    def branch(self, name: str, args: tuple[Expr, ...], stack: tuple[str, ...]) -> _Tr:
        first = self.go(args[0], stack)
        if name == "IF":
            return self.if_branch(args, first, stack)
        return self.choose_branch(args, first, stack)

    def if_branch(self, args: tuple[Expr, ...], first: _Tr, stack: tuple[str, ...]) -> _Tr:
        if len(args) < 3:
            _unsupported("IF", "without an else value, which is not measured")
        if_true, if_false = _filled(args[0])
        (yes, yes_fail), (no, no_fail) = (
            self.scoped(args[1], stack, self.filled | if_true),
            self.scoped(args[2], stack, self.filled | if_false),
        )
        # A "" beside a date is the blank of a nullable date: the date, failing (blank) there.
        for blank, other, i in ((yes, no, 1), (no, yes, 2)):
            if other.kind == "date" and blank.kind == "text" and _is_empty(args[i]):
                gap = dataclasses.replace(other)
                if i == 1:
                    yes, yes_fail = gap, ALWAYS
                else:
                    no, no_fail = gap, ALWAYS
                break
        self.same_kind("IF", [yes, no])
        cond = _cond(first)
        if first.truth is not None:  # both branches were still checked above
            self.value(yes), self.value(no)
            taken, fail = (yes, yes_fail) if first.truth else (no, no_fail)
            if fail:
                self.fails.append(fail)
            return taken
        if yes_fail or no_fail:
            self.fails.append(f"if({cond}, {yes_fail or NEVER}, {no_fail or NEVER})")
        return self.joined(f"if({cond}, {self.value(yes)}, {self.value(no)})", [yes, no])

    def choose_branch(self, args: tuple[Expr, ...], first: _Tr, stack: tuple[str, ...]) -> _Tr:
        name = "CHOOSE"
        index = _num(first, name)
        scoped = [self.scoped(arg, stack, self.filled) for arg in args[1:]]
        options = [tr for tr, _ in scoped]
        self.same_kind(name, options)
        reach = _whole_values(args[0])
        if reach is None or not reach <= set(range(1, len(options) + 1)):
            _unsupported(name, "with an index not provably a whole number in range")
        if first.values is not None and len(first.values) == 1:  # a constant index
            for option in options:
                self.value(option)
            (chosen,) = first.values
            if scoped[int(chosen) - 1][1]:
                self.fails.append(scoped[int(chosen) - 1][1])
            return options[int(chosen) - 1]
        # The index is proven in range, so the last value is simply the else.
        code, fail = self.value(options[-1]), scoped[-1][1]
        for i in range(len(options) - 1, 0, -1):
            code = f"if({index} == {i}, {self.value(options[i - 1])}, {code})"
            if fail or scoped[i - 1][1]:
                fail = f"if({index} == {i}, {scoped[i - 1][1] or NEVER}, {fail or NEVER})"
        if fail:
            self.fails.append(fail)
        return self.joined(code, options)

    @staticmethod
    def joined(code: str, options: list[_Tr]) -> _Tr:
        return _Tr(
            code,
            options[0].kind,
            _union(*options),
            integral=all(o.whole for o in options),
            moment=any(o.moment for o in options),
            instant=next((o.instant for o in options if o.instant), ""),
        )

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
    def extremes(name: str, vals: list[_Tr]) -> frozenset[float] | None:
        pick = min if name == "MIN" else max
        found = vals[0]
        for nxt in vals[1:]:
            found = _Tr("", "number", _combine(found, nxt, pick))
        return found.values

    @staticmethod
    def extreme(name: str, parts: list[str]) -> str:
        sign = "<" if name == "MIN" else ">"
        code = parts[0]
        for part in parts[1:]:
            code = f"if({code} {sign} {part}, {code}, {part})"
            if len(code) > FORM_HEADER_MAX_CHARS:  # each step doubles the code, so stop early
                raise too_large(len(code))
        return code

    @staticmethod
    def round(args: tuple[Expr, ...], vals: list[_Tr]) -> _Tr:
        # Whole places only: fractional places differ in floating point (1.005).
        if _whole(args[1], "ROUND", 0) != 0:
            _unsupported(
                "ROUND", "with places other than 0, which a header cannot round the same way"
            )
        x = _num(vals[0], "ROUND")
        if not vals[0].whole:
            _unsupported("ROUND", "of a number not known to be whole, which is not measured")
        # Half away from zero, built from floor (Learn: floor) because the page lists no round.
        values = _mapped(vals[0], lambda v: -math.floor(0.5 - v) if v < 0 else math.floor(v + 0.5))
        code = f"if({x} < 0, 0 - floor(0 - {x} + 0.5), floor({x} + 0.5))"
        return _Tr(code, "number", values, integral=True)

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


def tabulate(expr: Expr, ctx: TranslationContext) -> str | None:
    """The nested table for a sub-formula that reads only choice columns, or None."""
    table = _Translator(ctx).table(expr)
    return None if table is None else table.code


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
    code = _Translator.value(tr)
    if tr.kind != declared:
        _refuse(
            FindingCode.FORM_FORMULA_RESULT_UNSUPPORTED,
            f"returns a {tr.kind} but the column is {declared}",
        )
    if tr.kind == "date":
        return _date_result(translator, tr)
    if translator.fails:
        # A value outside what the arithmetic proves is left blank rather than shown wrong.
        code = f"if({_any(translator.fails)}, '', {code})"
    if len(code) > FORM_HEADER_MAX_CHARS:
        raise too_large(len(code))
    return Translation("=" + code, declared)


def _date_result(translator: _Translator, tr: _Tr) -> Translation:
    if tr.moment:
        _refuse(
            FindingCode.FORM_FORMULA_RESULT_UNSUPPORTED,
            "returns a date and time value, whose display is not measured",
        )
    # The day is shown through the calendar parts, so it must be where they are exact.
    translator.civil("the result", tr)
    blank = _any(translator.fails)
    code = f"if({blank}, '', {tr.code})" if blank else tr.code
    if len(code) > FORM_HEADER_MAX_CHARS:
        raise too_large(len(code))
    return Translation("=" + code, "date", tr.code, blank)
