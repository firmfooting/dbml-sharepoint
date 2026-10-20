"""A reference evaluator for calculated-column formulas, for parity tests only.

Only what test/_formula_facts.py measured is pinned (blank coercion, DATE overflow, text
equality, a system date column plus days); every other function follows the usual spreadsheet
rule and is exercised only through the grid. A case nobody measured raises NotImplementedError
rather than guess.

A date column holds a `datetime.date`: the site-local calendar day. Its UTC instant is site-local
midnight, so `2027-01-04T13:00:00Z` at +11 is the date 2027-01-05. A system date column (Created)
holds an aware `datetime.datetime` instant; its day is taken in the site zone.
"""

import math
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import cast
from zoneinfo import ZoneInfo

from dbml_sharepoint.analysis.formula.syntax import (
    Binary,
    Call,
    ColumnKind,
    Expr,
    Neg,
    Num,
    Percent,
    Ref,
    Text,
)

DEFAULT_ZONE = "Australia/Melbourne"
_SERIAL_ZERO = date(1899, 12, 30)


@dataclass(frozen=True, slots=True)
class ColumnError:
    """What a calculated column shows instead of a value; `code` is the `#n` of `error;#n`."""

    code: int


ERROR = ColumnError

type Value = str | float | bool | date | datetime | ColumnError | None


def _local(moment: datetime, zone: str) -> date:
    return moment.astimezone(ZoneInfo(zone)).date()


def _serial(value: date | datetime, zone: str) -> float:
    # A datetime reads as the site's clock, so a UTC midnight at +11 is 11:00 of that day.
    if isinstance(value, datetime):
        local = value.astimezone(ZoneInfo(zone))
        return (local.date() - _SERIAL_ZERO).days + (
            local.hour * 3600 + local.minute * 60 + local.second
        ) / 86400
    return float((value - _SERIAL_ZERO).days)


def _number(value: Value, zone: str) -> float | ColumnError:
    """Blank counts as 0 in arithmetic; text and choice values are a value error (#1)."""
    if isinstance(value, ColumnError):
        return value
    if value is None:
        return 0.0
    if isinstance(value, str):
        return ColumnError(1)
    if isinstance(value, date):  # datetime is a date
        return _serial(value, zone)
    return float(value)


def _text(value: Value, zone: str) -> str | ColumnError:
    if isinstance(value, ColumnError | str):
        return value
    if value is None:
        return ""
    if isinstance(value, bool):
        raise NotImplementedError("a yes/no value joined as text is not measured")
    number = _number(value, zone)
    assert isinstance(number, float)
    return f"{number:.15g}"


def _shift(value: date | datetime, days: float, zone: str) -> date:
    if days != int(days):
        raise NotImplementedError("a fractional number of days is not measured")
    day = _local(value, zone) if isinstance(value, datetime) else value
    return day + timedelta(days=int(days))


def _power(base: float, exponent: float) -> float | ColumnError:
    if base == 0 and exponent == 0:
        return ColumnError(5)
    try:
        result = base**exponent
    except ZeroDivisionError:  # 0 to a negative power: the code is unmeasured
        return ColumnError(0)
    except OverflowError:
        return ColumnError(5)
    return ColumnError(5) if isinstance(result, complex) else result


def _arithmetic(op: str, left: Value, right: Value, zone: str) -> Value:
    moments = [isinstance(v, date) for v in (left, right)]
    blank = left is None or right is None
    if op in "+-" and any(moments) and not blank:
        a, b = left, right
        if isinstance(a, date) and isinstance(b, date):
            if op == "+":
                raise NotImplementedError("date plus date is not measured")
            return _serial(a, zone) - _serial(b, zone)
        if isinstance(a, date) and isinstance(b, int | float):
            return _shift(a, b if op == "+" else -b, zone)
        if op == "+" and isinstance(a, int | float) and isinstance(b, date):
            return _shift(b, a, zone)
    a, b = _number(left, zone), _number(right, zone)
    if isinstance(a, ColumnError):
        return a
    if isinstance(b, ColumnError):
        return b
    match op:
        case "+":
            return a + b
        case "-":
            return a - b
        case "*":
            return a * b
        case "/":
            return ColumnError(0) if b == 0 else a / b
    return _power(a, b)


def _order(left: Value, right: Value, zone: str) -> int:
    """-1, 0 or 1. A blank takes the zero of the other operand's type; two blanks are two zeros."""
    pair: list[str | float] = []
    for value, other in ((left, right), (right, left)):
        if value is None:
            pair.append("" if isinstance(other, str) else 0.0)
        elif isinstance(value, str):
            pair.append(value.casefold())  # text comparison ignores case
        else:
            number = _number(value, zone)
            assert isinstance(number, float)
            pair.append(number)
    a, b = pair
    if isinstance(a, str) and isinstance(b, str):
        return (a > b) - (a < b)
    if isinstance(a, float) and isinstance(b, float):
        return (a > b) - (a < b)
    raise NotImplementedError("comparing text with a number is not measured")


_COMPARE: dict[str, Callable[[int], bool]] = {
    "=": lambda o: o == 0,
    "<>": lambda o: o != 0,
    # Ordering of text (< > <= >=) is unmeasured; only = and <> were measured.
    "<": lambda o: o < 0,
    ">": lambda o: o > 0,
    "<=": lambda o: o <= 0,
    ">=": lambda o: o >= 0,
}


def _truth(value: Value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, float | int):
        return value != 0
    raise NotImplementedError("a blank or text condition is not measured")


def _numbers(name: str, values: list[Value]) -> list[float]:
    """Number arguments of a function; a blank, text or date argument is unmeasured."""
    found: list[float] = []
    for value in values:
        if value is None or isinstance(value, str | bool | date):
            raise NotImplementedError(f"{name} with a blank, text or date argument is unmeasured")
        assert not isinstance(value, ColumnError)
        found.append(float(value))
    return found


def _texts(values: list[Value], zone: str) -> list[str]:
    # A blank joins as "" (the measured `&` rule, assumed for text functions).
    return [t for t in (_text(v, zone) for v in values) if isinstance(t, str)]


def _only(value: Value, kinds: tuple[type, ...], what: str) -> object:
    if not isinstance(value, kinds) or isinstance(value, bool):
        raise NotImplementedError(f"{what} of a blank or mistyped value is not measured")
    return value


def _round(value: float, places: float) -> float:
    exponent = Decimal(1).scaleb(-int(places))
    return float(Decimal(repr(value)).quantize(exponent, rounding=ROUND_HALF_UP))


def _date(y: float, m: float, d: float) -> date | ColumnError:
    year, month = int(y) + (int(m) - 1) // 12, (int(m) - 1) % 12 + 1
    try:
        return date(year, month, 1) + timedelta(days=int(d) - 1)
    except ValueError, OverflowError:
        return ColumnError(5)


def _call(name: str, args: tuple[Expr, ...], run: Callable[[Expr], Value], zone: str) -> Value:
    if name == "IF":
        condition = run(args[0])
        if isinstance(condition, ColumnError):
            return condition
        if not _truth(condition) and len(args) < 3:
            raise NotImplementedError("IF without an else is unmeasured")
        return run(args[1] if _truth(condition) else args[2])
    if name == "CHOOSE":
        index = _number(run(args[0]), zone)
        if isinstance(index, ColumnError):
            return index
        if not 1 <= int(index) < len(args):
            raise NotImplementedError("CHOOSE with an index out of range is unmeasured")
        return run(args[int(index)])
    values = [run(arg) for arg in args]
    if failed := next((v for v in values if isinstance(v, ColumnError)), None):
        return failed
    first = values[0]
    match name:
        case "AND":
            return all(_truth(v) for v in values)
        case "OR":
            return any(_truth(v) for v in values)
        case "NOT":
            return not _truth(first)
        case "ISBLANK":
            return first is None
        case "MIN" | "MAX":
            return (min if name == "MIN" else max)(_numbers(name, values))
        case "ABS" | "INT":
            n = _numbers(name, values)[0]
            return abs(n) if name == "ABS" else math.floor(n)
        case "ROUND":
            n, places = _numbers(name, values)
            return _round(n, places)
        case "CONCATENATE":
            return "".join(_texts(values, zone))
        case "LEFT" | "RIGHT" | "MID" | "LEN" | "LOWER" | "UPPER" | "TRIM":
            return _text_function(name, _texts(values[:1], zone)[0], _numbers(name, values[1:]))
        case "DATE":
            y, m, d = _numbers(name, values)
            return _date(y, m, d)
        case "YEAR" | "MONTH" | "DAY":
            moment = _only(first, (date,), name)
            assert isinstance(moment, date)
            day = _local(moment, zone) if isinstance(moment, datetime) else moment
            return float({"YEAR": day.year, "MONTH": day.month, "DAY": day.day}[name])
    raise NotImplementedError(f"the reference evaluator has no {name}")


def _text_function(name: str, s: str, nums: list[float]) -> Value:
    count = nums[0] if nums else 1.0
    match name:
        case "LEFT":
            return s[: int(count)]
        case "RIGHT":
            return s[max(len(s) - int(count), 0) :] if int(count) else ""
        case "MID":
            return s[int(count) - 1 : int(count) - 1 + int(nums[1])]
        case "LEN":
            return float(len(s))
        case "LOWER":
            return s.lower()
        case "UPPER":
            return s.upper()
    return re.sub(" +", " ", s).strip(" ")  # TRIM keeps one space between words


def evaluate(
    expr: Expr,
    row: Mapping[str, object],
    kinds: Mapping[str, ColumnKind],
    *,
    zone: str = DEFAULT_ZONE,
) -> Value:
    """The calculated value of `expr` on `row`; `None` is blank, `ColumnError` a column error."""

    def run(node: Expr) -> Value:
        match node:
            case Num(value):
                return value
            case Text(value):
                return value
            case Ref(name):
                value = row.get(name)
                if kinds.get(name) == "number" and isinstance(value, int | float):
                    return float(value)
                return cast("Value", value)
            case Neg(operand):
                n = _number(run(operand), zone)
                return n if isinstance(n, ColumnError) else -n
            case Percent(operand):
                n = _number(run(operand), zone)
                return n if isinstance(n, ColumnError) else n / 100
            case Binary(op, left, right):
                a, b = run(left), run(right)
                if failed := next((v for v in (a, b) if isinstance(v, ColumnError)), None):
                    return failed
                if op == "&":
                    return _join(a, b, zone)
                if op in _COMPARE:
                    return _COMPARE[op](_order(a, b, zone))
                return _arithmetic(op, a, b, zone)
            case Call(name, args):
                return _call(name, args, run, zone)
        raise AssertionError(node)

    return run(expr)


def _join(a: Value, b: Value, zone: str) -> str | ColumnError:
    left, right = _text(a, zone), _text(b, zone)
    return (
        left
        if isinstance(left, ColumnError)
        else right
        if isinstance(right, ColumnError)
        else left + right
    )


def instant(day: date, zone: str) -> str:
    """The UTC instant of site-local midnight on `day`, as a list read returns it."""
    local = datetime(day.year, day.month, day.day, tzinfo=ZoneInfo(zone))
    return local.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
