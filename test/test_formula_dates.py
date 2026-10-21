"""Date formulas: day numbers on the site calendar, date columns read through epoch milliseconds.

A date inside a formula is a day number, so these formulas have no browser zone to depend on. A
date column is `Number([$D])`; a date and time value (and Created or Modified) becomes its site
day with the zone rule. Shapes with no measured behaviour are pinned below as refusals.
"""

import calendar
import re
from datetime import UTC, date, datetime, timedelta
from functools import cache
from zoneinfo import ZoneInfo

import pytest
from _format_eval import date_field, evaluate_expression, evaluate_rows
from _formula_facts import (
    BLANK_DATE_FIELD,
    BROWSER_PARTS_OF_DATE_ONLY,
    DATE_FIELD_EPOCH_MS,
    DATE_ONLY_STORED_AS_WRITTEN,
    DATE_OVERFLOW,
    HEADER_SIZE_LIMIT,
)
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
from dbml_sharepoint.analysis.formula.zone import out_of_span_instant, site_day, zone_rule
from dbml_sharepoint.analysis.limits import FORMATTER_SAVED_SIZE_FLOOR
from dbml_sharepoint.analysis.timezones import ZoneTable, known_zones

SITE = "Australia/Melbourne"
KINDS: dict[str, ColumnKind] = {
    "Status": "choice",
    "Created": "date",
    "Due": "date",
    "Seen": "date",
}
MOMENTS = frozenset({"Seen"})  # a date and time column; Created is one too
CHOICES = {"Status": ("Open", "Closed")}
# The site zone, a zone eight hours behind it, UTC, a zone west of UTC and one east of the site.
BROWSERS = (SITE, "Europe/Athens", "UTC", "America/Los_Angeles", "Pacific/Auckland")
_NOW = "2026-10-20T12:00:00Z"
_OPEN = 'IF([Status]="Open",{},{})'


def _ctx(formula: str, result: str, more: dict[str, str], site: str = SITE) -> TranslationContext:
    return TranslationContext(
        formulas={"Calc": formula, **more},
        kinds=KINDS,
        result_types={"Calc": result, **dict.fromkeys(more, "date")},
        choices=CHOICES,
        zone=site,
        moments=MOMENTS,
    )


def _translate(formula: str, result: str = "number", **more: str) -> str:
    return translate_column("Calc", _ctx(formula, result, more)).expression


def _parity(formula: str, result: str = "number", site: str = SITE, **more: str) -> str:
    ctx = _ctx(formula, result, more, site)
    expression = translate_column("Calc", ctx).expression
    check_parity(
        formula, expression, ctx.formulas, KINDS, CHOICES, BROWSERS, zone=site, moments=MOMENTS
    )
    return expression


def _run(expression: str, row: dict[str, object] | None = None) -> object:
    return evaluate_expression(expression, row or {}, browser_tz="UTC", now=_NOW)


def _refusal(formula: str, result: str = "number", **more: str) -> FormulaRefusal:
    with pytest.raises(FormulaRefusal) as found:
        translate_column("Calc", _ctx(formula, result, more))
    return found.value


def _ymd(date_formula: str) -> str:
    return f"YEAR({date_formula})*10000+MONTH({date_formula})*100+DAY({date_formula})"


def _day_ms(day: date) -> dict[str, int | None]:
    return date_field((day - date(1970, 1, 1)).days * 86_400_000)


def _ms(moment: datetime) -> dict[str, int | None]:
    return date_field(int(moment.timestamp() * 1000))


node = pytest.mark.skipif(NODE is None, reason="node is required")


_DUE = {"D": f"DATE(2026,{_OPEN.format('1', '11')},31)"}
_SHIFTED = 'DATE(YEAR([D]),MONTH([D])+IF([Status]="Open",12,3),DAY([D]))'
_FIRST = f"DATE(2026,3,{_OPEN.format('1', '31')})"
_FILLED = "IF(ISBLANK([Due]),{},{})"
_SEEN = "IF(ISBLANK([Seen]),{},{})"
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
    "date-only parts": (_FILLED.format("0", _ymd("[Due]")), "number", {}),
    "date-only filled test": (f"IF(NOT(ISBLANK([Due])),{_ymd('[Due]')},0)", "number", {}),
    "date-only filled and a choice": (
        f'IF(AND(NOT(ISBLANK([Due])),[Status]="Open"),{_ymd("[Due]")},0)',
        "number",
        {},
    ),
    "date-only blank or a choice": (
        f'IF(OR(ISBLANK([Due]),[Status]="Closed"),0,{_ymd("[Due]")})',
        "number",
        {},
    ),
    "date-only blank text": (_FILLED.format('"blank"', '"filled"'), "text", {}),
    "date-only plus days": (_FILLED.format("0", _ymd("[Due]+30")), "number", {}),
    "date-only minus days": (_FILLED.format("0", _ymd("[Due]-45")), "number", {}),
    "date-only month arithmetic": (
        _FILLED.format("0", _ymd("DATE(YEAR([Due]),MONTH([Due])+1,DAY([Due]))")),
        "number",
        {},
    ),
    "date-only month-end clamp": (
        _FILLED.format("0", _ymd("DATE(YEAR([Due]),MONTH([Due])+3,MIN(DAY([Due]),28))")),
        "number",
        {},
    ),
    "date-only difference": (_FILLED.format("0", "[Due]-DATE(2026,1,1)"), "number", {}),
    "date-only comparison": (
        _FILLED.format('"none"', 'IF([Due]>DATE(2026,3,15),"late","early")'),
        "text",
        {},
    ),
    "date-only equality": (
        _FILLED.format('"none"', 'IF([Due]=DATE(2026,10,4),"same","other")'),
        "text",
        {},
    ),
    "created parts": (_ymd("[Created]"), "number", {}),
    "created plus days": (_ymd("[Created]+30"), "number", {}),
    "created minus days": (_ymd("[Created]-1"), "number", {}),
    "created compared with a date": (
        _FILLED.format('"none"', 'IF([Created]+0>[Due],"after","on or before")'),
        "text",
        {},
    ),
    "created days since a date": (_FILLED.format("0", "([Created]+0)-[Due]"), "number", {}),
    "date-time parts": (_SEEN.format("0", _ymd("[Seen]")), "number", {}),
    "date-time plus days": (_SEEN.format("0", _ymd("[Seen]+1")), "number", {}),
    "date-time blank text": (
        _SEEN.format('"blank"', 'IF([Seen]+0=DATE(2026,10,4),"same","other")'),
        "text",
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
@pytest.mark.parametrize(
    "site", ["America/Los_Angeles", "Europe/London", "Pacific/Auckland", "UTC"]
)
def test_a_date_and_time_column_is_read_in_other_site_zones(site: str) -> None:
    for formula, result in (
        (_ymd("[Created]+3"), "number"),
        ("IF(DATE(YEAR([Created]),MONTH([Created])+1,DAY([Created]))>[Created]+0,1,0)", "number"),
    ):
        _parity(formula, result, site=site)


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


def test_the_saved_size_floor_is_the_largest_formatter_the_probe_saved() -> None:
    assert HEADER_SIZE_LIMIT["largest_saved"] == FORMATTER_SAVED_SIZE_FLOOR


def test_the_date_functions_each_have_a_parity_case() -> None:
    names = set().union(*(function_names(parse_formula(f)) for f, _, _ in PARITY.values()))
    assert {"DATE", "YEAR", "MONTH", "DAY"} <= names


# formula, result, code, what the detail must name
_FN = FindingCode.FORM_FORMULA_FUNCTION_UNSUPPORTED
_COLUMN = FindingCode.FORM_FORMULA_COLUMN_UNSUPPORTED
_RESULT = FindingCode.FORM_FORMULA_RESULT_UNSUPPORTED
REFUSED = [
    # A date column that can be blank, read outside the branch an ISBLANK test leaves it filled in.
    ("[Due]+1", "number", _COLUMN, "Due"),
    ("YEAR([Seen])", "number", _COLUMN, "Seen"),
    ("IF(ISBLANK([Due]),0,1)+DAY([Due])", "number", _COLUMN, "Due"),
    ("IF(NOT(ISBLANK([Due])),0,DAY([Due]))", "number", _COLUMN, "Due"),
    ("IF(OR(NOT(ISBLANK([Due])),[Status]=\"Open\"),DAY([Due]),0)", "number", _COLUMN, "Due"),
    ("IF(AND(ISBLANK([Due]),[Status]=\"Open\"),0,DAY([Due]))", "number", _COLUMN, "Due"),
    # A time of day is not measured: comparing, subtracting or returning a date and time value.
    ("[Created]-DATE(2026,1,1)", "number", _FN, "-"),
    ('IF([Created]>DATE(2026,1,1),"a","b")', "text", _FN, ">"),
    ('IF([Created]=[Created],"a","b")', "text", _FN, "="),
    ("[Created]", "date", _RESULT, "display"),
    ("DATE(2026,1,1)", "date", _RESULT, "display"),
    ("[Created]+1", "date", _RESULT, "display"),
    ("ISBLANK([Created])", "number", _FN, "ISBLANK"),
    ("MIN(DATE(2026,1,1),DATE(2026,2,1))", "number", _FN, "MIN"),
    ("MAX([Created]+0,DATE(2026,2,1))", "number", _FN, "MAX"),
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


def test_a_date_and_time_column_in_a_zone_without_a_rule_is_refused_by_name() -> None:
    name = _zone_where(r"only from (\d{4})", 2026, 2049)
    ctx = TranslationContext(
        formulas={"Calc": "YEAR([Created])"},
        kinds=KINDS,
        result_types={"Calc": "number"},
        choices=CHOICES,
        zone=name,
    )
    with pytest.raises(FormulaRefusal) as found:
        translate_column("Calc", ctx)
    assert found.value.code is FindingCode.FORM_FORMULA_ZONE_UNSUPPORTED
    assert name in found.value.detail


def test_a_date_only_column_needs_the_zone_too() -> None:
    name = _zone_where(r"only from (\d{4})", 2026, 2049)
    ctx = TranslationContext(
        formulas={"Calc": "IF(ISBLANK([Due]),0,DAY([Due]+1))"},
        kinds=KINDS,
        result_types={"Calc": "number"},
        choices=CHOICES,
        zone=name,
    )
    with pytest.raises(FormulaRefusal) as found:
        translate_column("Calc", ctx)
    assert found.value.code is FindingCode.FORM_FORMULA_ZONE_UNSUPPORTED


@node
@pytest.mark.parametrize(("written", "fact"), DATE_ONLY_STORED_AS_WRITTEN.items())
def test_a_date_only_column_shows_the_site_day_of_the_instant_it_kept(
    written: str, fact: dict[str, str]
) -> None:
    expression = _translate(_FILLED.format("0", "DAY([Due])"))
    ms = int(datetime.fromisoformat(fact["read_back"]).timestamp() * 1000)
    shown = int(fact["displayed"].split("/")[0])
    for browser in BROWSERS:
        got = evaluate_expression(expression, {"Due": date_field(ms)}, browser_tz=browser, now=_NOW)
        assert got == shown, (written, browser)


def test_a_fixed_offset_zone_has_no_span_guard_and_is_exact_for_any_instant() -> None:
    ctx = _ctx("YEAR([Created])", "number", {}, "Australia/Brisbane")
    expression = translate_column("Calc", ctx).expression
    guard = out_of_span_instant("Number([$Created])", zone_rule("Australia/Brisbane"))
    assert guard not in expression
    if NODE is None:
        return
    old, new = datetime(1999, 12, 31, 14, 30, tzinfo=UTC), datetime(2060, 6, 30, 14, 30, tzinfo=UTC)
    rows = [{"Created": _ms(old)}, {"Created": _ms(new)}]
    assert evaluate_rows(expression, rows, browser_tz="UTC", now=_NOW) == [2000, 2060]


def test_a_created_expression_stays_under_the_saved_size_floor() -> None:
    for formula in (
        "YEAR([Created])",
        _ymd("[Created]+7"),
        "DAY(DATE(YEAR([Created]),MONTH([Created])+1,MIN(DAY([Created]),28)))",
    ):
        assert len(_translate(formula)) < FORMATTER_SAVED_SIZE_FLOOR


def test_no_translation_reads_a_date_through_the_browser_zone() -> None:
    expression = _translate(_FILLED.format("0", f"{_ymd('[Due]')}+{_ymd('[Created]')}"), "number")
    for reader in ("getDate", "getMonth", "getYear", "getFullYear", "Date(", "toLocale"):
        assert reader not in expression
    assert "Number([$Due])" in expression
    assert "toString([$Due]) == ''" in expression


def test_a_site_zone_west_of_utc_writes_no_negative_literal() -> None:
    # The syntax reference lists no unary minus, so the offsets are subtractions from 0.
    ctx = _ctx("YEAR([Created])", "number", {}, "America/Los_Angeles")
    expression = translate_column("Calc", ctx).expression
    assert "- -" not in expression
    assert "+ -" not in expression
    assert "(0 - 28800000)" in expression


# --------------------------------------------------------------------- date fields at runtime


@node
def test_the_evaluator_models_what_was_measured_of_a_date_field() -> None:
    for kind, cases in DATE_FIELD_EPOCH_MS.items():
        for stored, ms in cases.items():
            assert int(datetime.fromisoformat(stored).timestamp() * 1000) == ms, kind
            assert _run("=Number([$D])", {"D": date_field(ms)}) == ms
    blank: dict[str, object] = {"D": date_field(None)}
    assert _run("=Number([$D])", blank) == BLANK_DATE_FIELD["Number"]
    assert _run("=toString([$D])", blank) == BLANK_DATE_FIELD["toString"]
    assert (_run("=[$D] == ''", blank) is True) == BLANK_DATE_FIELD["equals_empty_text"]
    filled: dict[str, object] = {"D": date_field(1791072000000)}
    assert _run("=toString([$D]) == ''", filled) is False
    assert _run("=toString([$D]) == ''", blank) is True


@node
def test_the_browser_parts_of_a_date_only_value_move_with_the_browser_zone() -> None:
    # A stored UTC midnight is the day before for a part reader west of UTC.
    facts = BROWSER_PARTS_OF_DATE_ONLY
    row = {"D": date_field(DATE_FIELD_EPOCH_MS["date only"][facts["value"]])}
    read = {"getDate": "=getDate([$D])", "getMonth": "=getMonth([$D])", "getYear": "=getYear([$D])"}
    own = {
        part: evaluate_expression(text, row, browser_tz=facts["browser"], now=_NOW)
        for part, text in read.items()
    }
    assert own == {part: facts[part] for part in read}
    west = evaluate_expression(read["getDate"], row, browser_tz="America/Los_Angeles", now=_NOW)
    assert west == facts["getDate"] - 1


@node
def test_a_translation_is_blank_rather_than_wrong_outside_the_verified_years() -> None:
    expression = _translate("IF([Status]=\"Open\",1,YEAR([Created]))")
    old, new = datetime(2001, 6, 1, tzinfo=UTC), datetime(2026, 6, 1, tzinfo=UTC)
    rows = [
        {"Status": "Open", "Created": _ms(old)},
        {"Status": "Closed", "Created": _ms(old)},
        {"Status": "Closed", "Created": _ms(new)},
    ]
    assert evaluate_rows(expression, rows, browser_tz="UTC", now=_NOW) == [1, "", 2026]


@node
def test_a_date_only_value_outside_the_calendar_range_is_blank_where_it_is_read() -> None:
    # A fixed-offset site zone has no verified-years guard, so only the calendar range blanks.
    ctx = _ctx(_FILLED.format("0", "DAY([Due])"), "number", {}, "UTC")
    expression = translate_column("Calc", ctx).expression
    rows = [
        {"Due": _day_ms(date(1850, 1, 1))},
        {"Due": _day_ms(date(1904, 3, 1))},
        {"Due": _day_ms(date(2100, 2, 28))},
        {"Due": _day_ms(date(2100, 3, 1))},
        {"Due": date_field(None)},
    ]
    assert evaluate_rows(expression, rows, browser_tz="UTC", now=_NOW) == ["", 1, 28, "", 0]


@node
def test_a_date_built_from_a_column_outside_the_calendar_range_is_blank() -> None:
    next_year = "DAY(DATE(YEAR([Due])+1,MONTH([Due]),DAY([Due])))"
    ctx = _ctx(_FILLED.format("0", next_year), "number", {}, "UTC")
    expression = translate_column("Calc", ctx).expression
    rows = [{"Due": _day_ms(date(y, 3, 5))} for y in (2026, 2099, 1850)]
    assert evaluate_rows(expression, rows, browser_tz="UTC", now=_NOW) == [5, "", ""]


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

# ------------------------------------------------------------------ the site day of an instant

_SITE_DAY_ZONES = [SITE, "America/Los_Angeles", "Europe/London", "Pacific/Auckland", "UTC"]
_DAY_ZERO = date(1970, 1, 1)


def _site_days(name: str, instants: list[datetime]) -> tuple[list[object], list[int]]:
    rule = zone_rule(name)
    rows = [{"V": int(t.timestamp() * 1000)} for t in instants]
    got = evaluate_rows("=" + site_day("[$V]", rule), rows, browser_tz="UTC", now=_NOW)
    tz = ZoneInfo(name)
    return got, [(t.astimezone(tz).date() - _DAY_ZERO).days for t in instants]


def _transitions(name: str, rule: zone.ZoneRule) -> list[datetime]:
    table = timezones.zone_table(name)
    return [at for at, _ in table.transitions if rule.first_year <= at.year <= rule.last_year]


@node
@pytest.mark.parametrize("name", _SITE_DAY_ZONES)
def test_every_instant_around_a_change_and_a_midnight_has_the_right_site_day(name: str) -> None:
    rule = zone_rule(name)
    offsets = [timedelta(0)]
    for mark in (60, 61, 120, 121, 180):
        offsets += [timedelta(minutes=mark), timedelta(minutes=-mark)]
    offsets += [timedelta(seconds=1), timedelta(seconds=-1)]
    instants = [at + step for at in _transitions(name, rule) for step in offsets]
    # Local midnights, either side, for every day of the verified years.
    tz = ZoneInfo(name)
    day = date(rule.first_year, 1, 2)
    while day < date(rule.last_year + 1, 1, 1) - timedelta(days=2):
        midnight = datetime(day.year, day.month, day.day, tzinfo=tz).astimezone(UTC)
        instants += [midnight - timedelta(seconds=1), midnight, midnight + timedelta(seconds=1)]
        day += timedelta(days=1)
    got, expected = _site_days(name, instants)
    wrong = [(t, g, e) for t, g, e in zip(instants, got, expected, strict=True) if g != e]
    assert not wrong, wrong[:3]


@node
@pytest.mark.parametrize("name", _SITE_DAY_ZONES)
def test_the_site_day_follows_the_clock_a_day_either_side_of_new_year(name: str) -> None:
    rule = zone_rule(name)
    instants: list[datetime] = []
    for year in range(rule.first_year, rule.last_year + 1):
        start = datetime(year, 1, 1, tzinfo=UTC)
        instants += [start + timedelta(hours=h) for h in range(-30, 31, 3)]
    instants = [t for t in instants if _inside(rule, t)]
    got, expected = _site_days(name, instants)
    assert got == expected


def _inside(rule: zone.ZoneRule, moment: datetime) -> bool:
    return datetime(rule.first_year, 1, 1, tzinfo=UTC) <= moment < datetime(
        rule.last_year + 1, 1, 1, tzinfo=UTC
    )


def _in_span(name: str, instants: list[datetime]) -> list[object]:
    rule = zone_rule(name)
    rows = [{"V": int(t.timestamp() * 1000)} for t in instants]
    code = out_of_span_instant("[$V]", rule)
    return evaluate_rows("=" + code, rows, browser_tz="UTC", now=_NOW)


@node
def test_an_instant_in_the_verified_years_is_never_outside_them() -> None:
    first, last = zone_rule(SITE).first_year, zone_rule(SITE).last_year
    edges = [
        datetime(first, 1, 1, tzinfo=UTC) - timedelta(seconds=1),
        datetime(first, 1, 1, tzinfo=UTC),
        datetime(last + 1, 1, 1, tzinfo=UTC) - timedelta(seconds=1),
        datetime(last + 1, 1, 1, tzinfo=UTC),
        datetime(first - 1, 6, 1, tzinfo=UTC),
        datetime(last + 1, 6, 1, tzinfo=UTC),
    ]
    assert _in_span(SITE, edges) == [True, False, False, True, True, True]
