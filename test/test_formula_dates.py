"""Date formulas as whole-day arithmetic, and the zone rule reader.

A date inside a formula is a day number, so these formulas have no zone to depend on; what is
refused for lack of a documented formatting route is pinned below as a list of refusals.
"""

import calendar
import re
from datetime import UTC, date, datetime, timedelta
from functools import cache

import pytest
from _format_eval import evaluate_expression, evaluate_rows
from _formula_facts import DATE_OVERFLOW
from _formula_grid import check_parity
from _node import NODE

from dbml_sharepoint.analysis import timezones
from dbml_sharepoint.analysis.findings import FindingCode
from dbml_sharepoint.analysis.formula import zone
from dbml_sharepoint.analysis.formula.civil import (
    END_DAY,
    FIRST_DAY,
    days_of,
    from_day_number,
    parts_of,
)
from dbml_sharepoint.analysis.formula.functions import function_names
from dbml_sharepoint.analysis.formula.parse import parse_formula
from dbml_sharepoint.analysis.formula.refusal import FormulaRefusal
from dbml_sharepoint.analysis.formula.syntax import ColumnKind
from dbml_sharepoint.analysis.formula.translate import TranslationContext, translate_column
from dbml_sharepoint.analysis.formula.zone import zone_rule
from dbml_sharepoint.analysis.limits import FORMATTER_SAVED_SIZE_FLOOR
from dbml_sharepoint.analysis.timezones import ZoneTable, known_zones

SITE = "Australia/Melbourne"
KINDS: dict[str, ColumnKind] = {"Status": "choice", "Created": "date", "Due": "date"}
CHOICES = {"Status": ("Open", "Closed")}
# The site zone, a zone eight hours away, and UTC.
BROWSERS = (SITE, "America/Los_Angeles", "UTC")
_NOW = "2026-10-20T12:00:00Z"
_OPEN = 'IF([Status]="Open",{},{})'


def _ctx(formula: str, result: str, more: dict[str, str]) -> TranslationContext:
    return TranslationContext(
        formulas={"Calc": formula, **more},
        kinds=KINDS,
        result_types={"Calc": result, **dict.fromkeys(more, "date")},
        choices=CHOICES,
        zone=SITE,
    )


def _translate(formula: str, result: str = "number", **more: str) -> str:
    return translate_column("Calc", _ctx(formula, result, more)).expression


def _parity(formula: str, result: str = "number", **more: str) -> str:
    expression = _translate(formula, result, **more)
    ctx = _ctx(formula, result, more)
    check_parity(formula, expression, ctx.formulas, KINDS, CHOICES, BROWSERS, zone=SITE)
    return expression


def _run(expression: str, row: dict[str, object] | None = None) -> object:
    return evaluate_expression(expression, row or {}, browser_tz="UTC", now=_NOW)


def _refusal(formula: str, result: str = "number", **more: str) -> FormulaRefusal:
    with pytest.raises(FormulaRefusal) as found:
        translate_column("Calc", _ctx(formula, result, more))
    return found.value


def _ymd(date_formula: str) -> str:
    return f"YEAR({date_formula})*10000+MONTH({date_formula})*100+DAY({date_formula})"


node = pytest.mark.skipif(NODE is None, reason="node is required")


_DUE = {"D": f"DATE(2026,{_OPEN.format('1', '11')},31)"}
_SHIFTED = 'DATE(YEAR([D]),MONTH([D])+IF([Status]="Open",12,3),DAY([D]))'
_FIRST = f"DATE(2026,3,{_OPEN.format('1', '31')})"
# id -> (formula, result type, chained columns)
PARITY: dict[str, tuple[str, str, dict[str, str]]] = {
    "month arithmetic": (_ymd(_SHIFTED), "number", _DUE),
    # A clamp of the day to the shortest month, which compares no dates.
    "month-end clamp": (_ymd("DATE(YEAR([D]),MONTH([D])+3,MIN(DAY([D]),28))"), "number", _DUE),
    "difference": (f"{_FIRST}-DATE(2026,2,28)", "number", {}),
    "equal": (f'IF({_FIRST}-1=DATE(2026,2,{_OPEN.format("28", "27")}),"a","b")', "text", {}),
    "greater": (f'IF({_FIRST}>DATE(2026,3,15),"late","early")', "text", {}),
    "leap day": ("DAY(DATE(2024,3,1)-1)+DAY(DATE(2025,3,1)-1)*100", "number", {}),
    "untaken branch": ('IF([Status]="Open",1,YEAR(DATE(2050,1,1)))', "number", {}),
    "untaken branch with a choice": (
        f'IF([Status]="Open",1,YEAR(DATE({_OPEN.format("2026", "2099")},1,1)))',
        "number",
        {},
    ),
}


@node
@pytest.mark.parametrize(("formula", "result", "more"), PARITY.values(), ids=PARITY.keys())
def test_translation_matches_the_reference(
    formula: str, result: str, more: dict[str, str]
) -> None:
    _parity(formula, result, **more)


@node
@pytest.mark.parametrize("formula", list(DATE_OVERFLOW))
def test_date_overflow_month_13_day_0_feb_31_and_29_feb(formula: str) -> None:
    more = {"DateLeap": "DATE(2024,2,29)"} if "DateLeap" in formula else {}
    expression = _parity(_ymd(formula), **more)
    day, month, year = DATE_OVERFLOW[formula]["displayed"].split("/")
    assert _run(expression) == int(year) * 10000 + int(month) * 100 + int(day)


@node
def test_the_range_ends_are_exact() -> None:
    assert _run(_translate("DAY(DATE(1904,3,1))")) == 1
    assert _run(_translate(_ymd("DATE(2100,2,28)"))) == 21000228
    assert _run(_translate(_ymd("DATE(1904,3,1)-0"))) == 19040301


@pytest.mark.parametrize(
    "formula",
    [
        "DATE(2100,3,1)-DATE(2100,2,28)",
        'IF(DATE(2100,2,29)=DATE(2100,3,1),"a","b")',
        "DAY(DATE(1904,2,29))",
        "YEAR(DATE(2100,2,28)+5)",
        f"YEAR(DATE({_OPEN.format('2026', '2101')},1,1))",
        f'IF([Status]="Open",1,YEAR(DATE({_OPEN.format("2026", "2101")},1,1)))',
        "DAY(DATE(0,1,1))",
        "DAY(DATE(10000,1,1))",
    ],
)
def test_a_date_outside_the_exact_range_is_refused(formula: str) -> None:
    refusal = _refusal(formula, "text" if formula.startswith("IF(DATE") else "number")
    assert refusal.code is FindingCode.FORM_FORMULA_FUNCTION_UNSUPPORTED
    assert "1904" in refusal.detail or "years" in refusal.detail or "year" in refusal.detail


@node
def test_every_day_of_the_range_has_its_calendar_parts() -> None:
    days = list(range(FIRST_DAY, END_DAY))
    rows = [{"V": d} for d in days]
    year, month, day = (
        evaluate_rows("=" + p, rows, browser_tz="UTC", now=_NOW) for p in parts_of("[$V]")
    )
    wrong = [
        d
        for d, y, m, dom in zip(days, year, month, day, strict=True)
        if (y, m, dom) != _parts(d)
    ]
    assert not wrong, wrong[:3]


def _parts(day: int) -> tuple[int, int, int]:
    real = from_day_number(day)
    return real.year, real.month, real.day


def _calendar(y: int, m: int, d: int) -> int:
    real = date(y + (m - 1) // 12, (m - 1) % 12 + 1, 1) + timedelta(days=d - 1)
    return (real - date(1970, 1, 1)).days


@node
def test_days_of_carries_month_and_day_overflow() -> None:
    cases = [
        (y, m, d)
        for y in (1904, 1905, 2000, 2024, 2099)
        for m in range(-14, 30)
        for d in (-35, -1, 0, 1, 28, 29, 30, 31, 32, 70)
        if all(FIRST_DAY <= _calendar(y, m, n) < END_DAY for n in (1, d))
    ]
    rows = [{"Y": y, "M": m, "D": d} for y, m, d in cases]
    got = evaluate_rows("=" + days_of("[$Y]", "[$M]", "[$D]"), rows, browser_tz="UTC", now=_NOW)
    for (y, m, d), value in zip(cases, got, strict=True):
        assert value == _calendar(y, m, d), (y, m, d)


def test_a_date_with_too_many_possible_arguments_is_refused_quickly() -> None:
    # 18 values each for year, month and day is 5832 combinations, over the work bound.
    def many(base: int, bits: int) -> str:
        text = str(base)
        for n in range(bits):
            text = f'IF([Status]="s{n}",{text},{base + n + 1})'
        return text

    refusal = _refusal(f"DAY(DATE({many(2000, 17)},{many(1, 17)},{many(1, 17)}))")
    assert refusal.code is FindingCode.FORM_FORMULA_FUNCTION_UNSUPPORTED
    assert "DATE" in refusal.detail


def test_a_nested_date_that_outgrows_a_saved_formatter_is_refused() -> None:
    chain = {"D0": "DATE(2026,1,1)"}
    for n in range(1, 8):
        chain[f"D{n}"] = f"DATE(YEAR([D{n - 1}]),MONTH([D{n - 1}])+1,DAY([D{n - 1}]))"
    refusal = _refusal("DAY([D7])", **chain)
    assert refusal.code is FindingCode.FORM_FORMULA_FUNCTION_UNSUPPORTED
    assert "too large" in refusal.detail
    small = _translate("DAY([D2])", **{k: v for k, v in chain.items() if k in ("D0", "D1", "D2")})
    assert len(small) < FORMATTER_SAVED_SIZE_FLOOR


def test_the_date_functions_each_have_a_parity_case() -> None:
    names = set().union(*(function_names(parse_formula(f)) for f, _, _ in PARITY.values()))
    assert {"DATE", "YEAR", "MONTH", "DAY"} <= names


# formula, result, code, what the detail must name
_FN = FindingCode.FORM_FORMULA_FUNCTION_UNSUPPORTED
REFUSED = [
    ("[Due]+1", "number", FindingCode.FORM_FORMULA_COLUMN_UNSUPPORTED, "Due"),
    ("YEAR([Created])", "number", FindingCode.FORM_FORMULA_COLUMN_UNSUPPORTED, "Created"),
    ("DATE(2026,1,1)", "date", FindingCode.FORM_FORMULA_RESULT_UNSUPPORTED, "ISO 8601"),
    ("DATE(2026,1,1)+1", "date", FindingCode.FORM_FORMULA_RESULT_UNSUPPORTED, "ISO 8601"),
    ("MIN(DATE(2026,1,1),DATE(2026,2,1))", "number", _FN, "MIN"),
    ("DATE(2026,1,1)+DATE(2026,1,1)", "number", _FN, "+"),
    ("5-DATE(2026,1,1)", "number", _FN, "-"),
    ("IF(DATE(2026,1,1)>5,1,2)", "number", _FN, ">"),
    ("DATE(2026,1,1)+0.5", "number", _FN, "+"),
    ("DAY(DATE(2026,1,1/2))", "number", _FN, "DATE"),
    ("YEAR(5)", "number", _FN, "YEAR"),
    ("ISBLANK(DATE(2026,1,1))", "number", _FN, "ISBLANK"),
    ('DATE(2026,1,1)&"x"', "text", _FN, "&"),
    ("YEAR(TODAY())", "number", FindingCode.FORM_FORMULA_VOLATILE, "TODAY"),
]


@pytest.mark.parametrize(("formula", "result", "code", "named"), REFUSED)
def test_a_refusal_names_the_formula_and_what_it_refused(
    formula: str, result: str, code: FindingCode, named: str
) -> None:
    refusal = _refusal(formula, result)
    assert refusal.code is code
    assert named in refusal.detail
    assert formula in refusal.finding("Task", "Calc", formula).message


# --------------------------------------------------------------------------- the zone rule


def _nth_weekday(year: int, sw: zone.Switch) -> date:
    days = [d for d in calendar.Calendar().itermonthdates(year, sw.month) if d.month == sw.month]
    matching = [d for d in days if (d.weekday() + 1) % 7 == sw.weekday]
    return matching[sw.nth - 1] if sw.nth > 0 else matching[-1]


@pytest.mark.parametrize("name", [SITE, "America/Los_Angeles", "Europe/London", "Pacific/Auckland"])
def test_the_rule_reproduces_every_transition_of_its_verified_years(name: str) -> None:
    rule = zone_rule(name)
    assert rule.switches is not None
    assert rule.daylight is not None
    table = timezones.zone_table(name)
    found = {at: offset for at, offset in table.transitions if rule.first_year <= at.year <= 2049}
    expected = {}
    for year in range(rule.first_year, rule.last_year + 1):
        for sw, before, after in (
            (rule.switches[0], rule.standard, rule.daylight),
            (rule.switches[1], rule.daylight, rule.standard),
        ):
            wall = datetime.combine(_nth_weekday(year, sw), datetime.min.time()) + timedelta(
                minutes=sw.minute
            )
            expected[(wall - timedelta(minutes=before)).replace(tzinfo=UTC)] = after
    assert found == expected


def test_the_site_zone_rule_starts_where_its_rule_began() -> None:
    rule = zone_rule(SITE)
    assert (rule.standard, rule.daylight, rule.first_year, rule.last_year) == (600, 660, 2008, 2049)
    assert zone_rule("UTC").switches is None


@cache
def _refused() -> dict[str, str]:
    refused: dict[str, str] = {}
    for name in sorted(known_zones()):
        try:
            zone_rule(name)
        except FormulaRefusal as found:
            refused[name] = found.detail
    return refused


def _zone_where(pattern: str, low: int = 0, high: int = 9999) -> str:
    for name, why in _refused().items():
        found = re.search(pattern, why)
        if found and low <= int((found.groups() or ("0",))[0]) <= high:
            return name
    raise AssertionError(f"no zone is refused with {pattern!r} from {low} to {high}")


def _refuse(name: str) -> FormulaRefusal:
    with pytest.raises(FormulaRefusal) as found:
        zone_rule(name)
    return found.value


def test_a_zone_with_no_expressible_rule_is_refused_by_name() -> None:
    # Its rule moves year to year, so no weekday rule holds for more than the last few years.
    name = _zone_where(r"only from (\d{4})", 2026, 2049)
    refusal = _refuse(name)
    assert refusal.code is FindingCode.FORM_FORMULA_ZONE_UNSUPPORTED
    assert name in refusal.detail
    assert name in refusal.finding("Task", "Calc", "DATE(2026,1,1)").message


def test_a_zone_whose_rule_changed_inside_the_window_is_refused() -> None:
    # Regular now, but a different rule before a recent year, so extrapolating would be wrong.
    name = _zone_where(r"only from (\d{4})", 2011, 2025)
    assert _refuse(name).code is FindingCode.FORM_FORMULA_ZONE_UNSUPPORTED


def test_a_zone_with_a_switch_at_midnight_is_refused() -> None:
    name = _zone_where("near midnight")
    assert _refuse(name).code is FindingCode.FORM_FORMULA_ZONE_UNSUPPORTED


def test_a_zone_with_a_switch_near_new_year_is_refused() -> None:
    name = _zone_where("within a month of new year")
    assert _refuse(name).code is FindingCode.FORM_FORMULA_ZONE_UNSUPPORTED


def _synthetic(monkeypatch: pytest.MonkeyPatch, steps: list[tuple[datetime, int]]) -> None:
    table = ZoneTable(zone="Test/Synthetic", start_offset=0, transitions=tuple(steps))
    def fake(_name: str) -> ZoneTable:
        return table

    monkeypatch.setattr(zone, "zone_table", fake)


def test_a_zone_with_more_than_two_offsets_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    steps = [
        (datetime(2048, 3, 1, tzinfo=UTC), 60),
        (datetime(2048, 6, 1, tzinfo=UTC), 120),
        (datetime(2048, 9, 1, tzinfo=UTC), 180),
    ]
    _synthetic(monkeypatch, steps)
    with pytest.raises(FormulaRefusal, match="more than two"):
        zone_rule.__wrapped__("Test/Synthetic")


def test_a_zone_whose_switch_days_follow_no_weekday_rule_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    steps = []
    for year in range(2000, 2050):
        # Weekday-free dates: a different day of the month and weekday every year.
        steps.append((datetime(year, 3, 1 + (year * 7) % 28, 5, tzinfo=UTC), 60))
        steps.append((datetime(year, 10, 1 + (year * 11) % 28, 5, tzinfo=UTC), 0))
    _synthetic(monkeypatch, steps)
    with pytest.raises(FormulaRefusal, match="Test/Synthetic"):
        zone_rule.__wrapped__("Test/Synthetic")
