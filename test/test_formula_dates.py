"""Date formulas translated at site-local midnight, checked in every browser zone."""

import re
from datetime import UTC, date, datetime, timedelta
from functools import cache
from zoneinfo import ZoneInfo

import pytest
from _format_eval import evaluate_expression, evaluate_rows
from _formula_facts import CREATED_PLUS_DAYS_DAY, DATE_OVERFLOW
from _formula_grid import check_parity
from _node import NODE

from dbml_sharepoint.analysis.findings import FindingCode
from dbml_sharepoint.analysis.formula.refusal import FormulaRefusal
from dbml_sharepoint.analysis.formula.syntax import ColumnKind
from dbml_sharepoint.analysis.formula.translate import TranslationContext, translate_column
from dbml_sharepoint.analysis.formula.zone import (
    day_of_instant,
    days_of,
    local_midnight,
    midnight_ms,
    parts_of,
    zone_rule,
)
from dbml_sharepoint.analysis.timezones import known_zones

pytestmark = pytest.mark.skipif(NODE is None, reason="node is required")

SITE = "Australia/Melbourne"
KINDS: dict[str, ColumnKind] = {"Status": "choice", "Created": "date", "Due": "date"}
CHOICES = {"Status": ("Open", "Closed")}
# The site zone, a zone eight hours away, and UTC.
BROWSERS = (SITE, "America/Los_Angeles", "UTC")
ZONES = (SITE, "America/Los_Angeles", "Europe/London", "Pacific/Auckland", "Asia/Kolkata", "UTC")
_EPOCH = date(1970, 1, 1)
_NOW = "2026-10-20T12:00:00Z"


def _ctx(formula: str, result: str, zone: str, more: dict[str, str]) -> TranslationContext:
    return TranslationContext(
        formulas={"Calc": formula, **more},
        kinds=KINDS,
        result_types={"Calc": result, **dict.fromkeys(more, "date")},
        choices=CHOICES,
        zone=zone,
    )


def _parity(
    formula: str, *, result: str = "date", zone: str = SITE, **more: str
) -> str:
    ctx = _ctx(formula, result, zone, more)
    expression = translate_column("Calc", ctx).expression
    browsers = tuple(dict.fromkeys((zone, *BROWSERS)))
    check_parity(formula, expression, ctx.formulas, KINDS, CHOICES, browsers, zone=zone)
    return expression


def _run(expression: str, row: dict[str, object] | None = None, browser: str = "UTC") -> object:
    return evaluate_expression(expression, row or {}, browser_tz=browser, now=_NOW)


def _local_day(instant: object, zone: str) -> str:
    assert isinstance(instant, str)
    return datetime.fromisoformat(instant).astimezone(ZoneInfo(zone)).date().isoformat()


def _shown(text: str) -> str:
    day, month, year = text.split("/")
    return f"{year}-{int(month):02d}-{int(day):02d}"


def _refusal(formula: str, result: str = "date", zone: str = SITE, **more: str) -> FormulaRefusal:
    with pytest.raises(FormulaRefusal) as found:
        translate_column("Calc", _ctx(formula, result, zone, more))
    return found.value


def test_date_month_arithmetic_with_a_month_end_clamp() -> None:
    _parity('DATE(YEAR([D]),MONTH([D])+IF([Status]="Open",12,3),DAY([D]))', D="[Created]+0")
    # A clamp of the day to the shortest month, which carries no date comparison.
    _parity("DATE(YEAR([D]),MONTH([D])+3,MIN(DAY([D]),28))", D="[Created]+0")


def test_the_clamp_that_compares_two_dates_is_refused() -> None:
    clamp = "MIN(DATE(YEAR([D]),MONTH([D])+3,DAY([D])),DATE(YEAR([D]),MONTH([D])+4,1)-1)"
    refusal = _refusal(clamp, D="[Created]+0")
    assert refusal.code is FindingCode.FORM_FORMULA_FUNCTION_UNSUPPORTED
    assert "MIN" in refusal.detail


@pytest.mark.parametrize("formula", list(DATE_OVERFLOW))
def test_date_overflow_month_13_day_0_feb_31_and_29_feb(formula: str) -> None:
    more = {"DateLeap": "DATE(2024,2,29)"} if "DateLeap" in formula else {}
    expression = _parity(formula, **more)
    shown = _shown(DATE_OVERFLOW[formula]["displayed"])
    assert _local_day(_run(expression), SITE) == shown


def test_date_plus_days_is_taken_in_site_local_time() -> None:
    fact = CREATED_PLUS_DAYS_DAY
    row: dict[str, object] = {"Created": fact["created"]}
    for days, shown in ((0, fact["shown_zero"]), (1, fact["shown_one"])):
        expression = _parity(f"[Created]+{days}")
        assert _local_day(_run(expression, row), SITE) == shown


@pytest.mark.parametrize("zone", ZONES)
def test_the_due_day_flips_at_site_local_midnight_in_every_browser_zone(zone: str) -> None:
    # The grid holds either side of local midnight and noon on and around each daylight change.
    _parity("[Created]+1", zone=zone)
    _parity("[Created]-1", zone=zone)
    _parity("DATE(YEAR([Created]),MONTH([Created]),DAY([Created]))", zone=zone)
    _parity("IF([Created]+2>[Created]+1,[Created]+2,[Created]+1)", zone=zone)
    _parity("([Created]+10)-([Created]+3)", result="number", zone=zone)
    _parity('IF([Created]+3=[Created]+3,"same","different")', result="text", zone=zone)


def test_a_chained_date_column_feeds_the_next() -> None:
    _parity("DATE(YEAR([Next]),MONTH([Next])+1,DAY([Next]))", Next="[Created]+30")


def test_the_translation_is_the_same_whatever_the_browser_zone() -> None:
    expression = _parity("[Created]+1")
    row: dict[str, object] = {"Created": "2026-10-20T14:20:48Z"}
    assert len({_run(expression, row, browser) for browser in BROWSERS}) == 1


def _expected_midnight(day: int, zone: str) -> int:
    local = date.fromordinal(day + _EPOCH.toordinal())
    moment = datetime(local.year, local.month, local.day, tzinfo=ZoneInfo(zone))
    return int(moment.timestamp() * 1000)


@pytest.mark.parametrize("zone", ZONES)
def test_every_day_of_the_verified_years_has_the_right_midnight(zone: str) -> None:
    rule = zone_rule(zone)
    first = (date(rule.first_year, 1, 1) - _EPOCH).days
    last = (date(rule.last_year, 12, 31) - _EPOCH).days
    days = list(range(first, last + 1))
    got = evaluate_rows(
        "=" + midnight_ms("[$V]", rule), [{"V": d} for d in days], browser_tz="UTC", now=_NOW
    )
    wrong = [(d, g) for d, g in zip(days, got, strict=True) if g != _expected_midnight(d, zone)]
    assert not wrong, wrong[:3]


@pytest.mark.parametrize("zone", ZONES)
def test_every_instant_around_a_change_has_the_right_site_day(zone: str) -> None:
    rule = zone_rule(zone)
    zinfo = ZoneInfo(zone)
    start = datetime(rule.first_year, 1, 2, tzinfo=UTC)
    stamps = []
    while start.year <= rule.last_year - 0 and start < datetime(rule.last_year, 12, 30, tzinfo=UTC):
        stamps.append(start)
        start += timedelta(hours=11, minutes=59, seconds=59)
    # Dense either side of each change.
    for year in range(rule.first_year, rule.last_year + 1, 7):
        for month in range(1, 13):
            base = datetime(year, month, 1, tzinfo=UTC)
            stamps += [base + timedelta(minutes=30 * n) for n in range(0, 24 * 2 * 31, 7)]
    millis = [int(s.timestamp() * 1000) for s in stamps]
    got = evaluate_rows(
        "=" + day_of_instant("[$V]", rule), [{"V": m} for m in millis], browser_tz="UTC", now=_NOW
    )
    for stamp, value in zip(stamps, got, strict=True):
        assert value == (stamp.astimezone(zinfo).date() - _EPOCH).days, (stamp, value)


def test_the_calendar_arithmetic_matches_the_calendar() -> None:
    days = list(range((date(2000, 1, 1) - _EPOCH).days, (date(2049, 12, 31) - _EPOCH).days + 1))
    rows = [{"V": d} for d in days]
    rule = zone_rule("UTC")
    parts = [evaluate_rows("=" + p, rows, browser_tz="UTC", now=_NOW) for p in parts_of("[$V]")]
    for d, y, m, dom in zip(days, *parts, strict=True):
        real = _EPOCH + timedelta(days=d)
        assert (y, m, dom) == (real.year, real.month, real.day), real
    assert rule.first_year == 2000


def test_days_of_carries_month_and_day_overflow() -> None:
    cases = [
        (y, m, d)
        for y in (2000, 2001, 2024, 2049)
        for m in range(-14, 30)
        for d in (-35, -1, 0, 1, 28, 29, 30, 31, 32, 70)
    ]
    rows = [{"Y": y, "M": m, "D": d} for y, m, d in cases]
    got = evaluate_rows("=" + days_of("[$Y]", "[$M]", "[$D]"), rows, browser_tz="UTC", now=_NOW)
    for (y, m, d), value in zip(cases, got, strict=True):
        real = date(y + (m - 1) // 12, (m - 1) % 12 + 1, 1) + timedelta(days=d - 1)
        assert value == (real - _EPOCH).days, (y, m, d)


# Years outside the zone's verified span give the blank expression, whatever the browser's zone.
@pytest.mark.parametrize(
    ("zone", "formula"),
    [
        ("UTC", "DATE(1999,12,31)"),
        ("UTC", "DATE(2050,1,1)"),
        ("UTC", "DATE(2026,12,1)+9999"),
        ("UTC", "DATE(1999,6,1)+0"),
        (SITE, "DATE(2007,12,31)"),
        (SITE, "DATE(2026,1,0-20000)"),
    ],
)
def test_a_date_outside_the_verified_years_is_blank(zone: str, formula: str) -> None:
    expression = translate_column("Calc", _ctx(formula, "date", zone, {})).expression
    assert _run(expression, browser=zone) == ""


def test_a_date_function_of_an_out_of_span_date_is_blank() -> None:
    expression = translate_column("Calc", _ctx("YEAR(DATE(2050,3,1))", "number", "UTC", {}))
    assert _run(expression.expression) == ""
    inside = translate_column("Calc", _ctx("YEAR(DATE(2049,12,31))", "number", "UTC", {}))
    assert _run(inside.expression) == 2049


def test_the_boundary_years_of_the_span_are_translated() -> None:
    rule = zone_rule(SITE)
    ctx = _ctx(f"DATE({rule.first_year},1,1)", "date", SITE, {})
    assert _local_day(_run(translate_column("Calc", ctx).expression), SITE) == (
        f"{rule.first_year}-01-01"
    )
    ctx = _ctx(f"DATE({rule.last_year},12,31)", "date", SITE, {})
    assert _local_day(_run(translate_column("Calc", ctx).expression), SITE) == (
        f"{rule.last_year}-12-31"
    )


def test_local_midnight_guards_its_year_and_includes_the_offset() -> None:
    rule = zone_rule(SITE)
    expression = "=" + local_midnight("[$Y]", "[$M]", "[$D]", rule)
    rows = [
        {"Y": 2026, "M": 1, "D": 15},
        {"Y": 2026, "M": 7, "D": 15},
        {"Y": 1999, "M": 7, "D": 15},
        {"Y": 2050, "M": 7, "D": 15},
    ]
    got = evaluate_rows(expression, rows, browser_tz="UTC", now=_NOW)
    assert got == ["2026-01-14T13:00:00.000Z", "2026-07-14T14:00:00.000Z", "", ""]


def test_a_stored_date_column_is_refused_because_a_blank_date_is_undocumented() -> None:
    refusal = _refusal("[Due]+1")
    assert refusal.code is FindingCode.FORM_FORMULA_COLUMN_UNSUPPORTED
    assert "Due" in refusal.detail
    assert "blank" in refusal.detail


@cache
def _refused() -> dict[str, str]:
    refused: dict[str, str] = {}
    for name in sorted(known_zones()):
        try:
            zone_rule(name)
        except FormulaRefusal as found:
            refused[name] = found.detail
    return refused


def _zone_where(detail: str) -> str:
    matching = [name for name, why in _refused().items() if re.search(detail, why)]
    assert matching, detail
    return matching[0]


def _refused_from(low: int, high: int) -> str:
    """A refused zone whose rule holds only from a year in [low, high]."""
    for name, why in _refused().items():
        found = re.search(r"only from (\d{4})", why)
        if found and low <= int(found[1]) <= high:
            return name
    raise AssertionError((low, high))


def test_a_zone_with_no_expressible_rule_is_refused_by_name() -> None:
    # Its rule moves year to year, so no weekday rule holds for more than the last few years.
    name = _refused_from(2026, 2049)
    refusal = _refusal("DATE(2026,1,1)", zone=name)
    assert refusal.code is FindingCode.FORM_FORMULA_ZONE_UNSUPPORTED
    assert name in refusal.detail
    assert name in refusal.finding("Task", "Calc", "DATE(2026,1,1)").message


def test_a_zone_whose_rule_changed_inside_the_window_is_refused() -> None:
    # Regular now, but a different rule before a recent year, so extrapolating would be wrong.
    name = _refused_from(2011, 2025)
    refusal = _refusal("DATE(2026,1,1)", zone=name)
    assert refusal.code is FindingCode.FORM_FORMULA_ZONE_UNSUPPORTED
    assert name in refusal.detail


def test_a_zone_with_a_switch_at_midnight_is_refused() -> None:
    name = _zone_where("near midnight")
    assert _refusal("DATE(2026,1,1)", zone=name).code is FindingCode.FORM_FORMULA_ZONE_UNSUPPORTED


def test_a_zone_that_changed_before_the_window_end_is_still_translated_over_its_span() -> None:
    assert zone_rule(SITE).first_year > 2000
    assert zone_rule(SITE).last_year == 2049


def test_a_formula_with_no_dates_does_not_need_the_zone() -> None:
    name = _zone_where("near midnight")
    ctx = _ctx('IF([Status]="Open","a","b")', "text", name, {})
    assert translate_column("Calc", ctx).expression.startswith("=if(")


# formula, result, code, what the detail must name
REFUSED = [
    (
        "MIN(DATE(2026,1,1),DATE(2026,2,1))",
        "date",
        FindingCode.FORM_FORMULA_FUNCTION_UNSUPPORTED,
        "MIN",
    ),
    ("DATE(2026,1,1)+DATE(2026,1,1)", "date", FindingCode.FORM_FORMULA_FUNCTION_UNSUPPORTED, "+"),
    ("DATE(2026,1,1)>5", "text", FindingCode.FORM_FORMULA_FUNCTION_UNSUPPORTED, ">"),
    ("5-DATE(2026,1,1)", "number", FindingCode.FORM_FORMULA_FUNCTION_UNSUPPORTED, "-"),
    ("[Created]", "date", FindingCode.FORM_FORMULA_RESULT_UNSUPPORTED, "time of day"),
    ("[Created]-[Created]", "number", FindingCode.FORM_FORMULA_FUNCTION_UNSUPPORTED, "-"),
    ("[Created]>[Created]", "text", FindingCode.FORM_FORMULA_FUNCTION_UNSUPPORTED, ">"),
    ("[Created]+0.5", "date", FindingCode.FORM_FORMULA_FUNCTION_UNSUPPORTED, "+"),
    ("DATE(2026,1,1/2)", "date", FindingCode.FORM_FORMULA_FUNCTION_UNSUPPORTED, "DATE"),
    ("YEAR(5)", "number", FindingCode.FORM_FORMULA_FUNCTION_UNSUPPORTED, "YEAR"),
    ("ISBLANK(DATE(2026,1,1))", "number", FindingCode.FORM_FORMULA_FUNCTION_UNSUPPORTED, "ISBLANK"),
    ("DATE(2026,1,1)&\"x\"", "text", FindingCode.FORM_FORMULA_FUNCTION_UNSUPPORTED, "&"),
    ("TODAY()+1", "date", FindingCode.FORM_FORMULA_VOLATILE, "TODAY"),
]


@pytest.mark.parametrize(("formula", "result", "code", "named"), REFUSED)
def test_a_refusal_names_the_formula_and_what_it_refused(
    formula: str, result: str, code: FindingCode, named: str
) -> None:
    refusal = _refusal(formula, result)
    assert refusal.code is code
    assert named in refusal.detail
    assert formula in refusal.finding("Task", "Calc", formula).message


def test_nested_date_arithmetic_that_grows_too_large_is_refused() -> None:
    chain = {"D0": "[Created]+1"}
    for n in range(1, 6):
        chain[f"D{n}"] = f"DATE(YEAR([D{n - 1}]),MONTH([D{n - 1}])+1,DAY([D{n - 1}]))"
    refusal = _refusal("[D5]+0", **chain)
    assert refusal.code is FindingCode.FORM_FORMULA_FUNCTION_UNSUPPORTED
    assert "too large" in refusal.detail
