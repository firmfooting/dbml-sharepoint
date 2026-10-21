"""A calculated date in a header: re-derived inline, shown through a date order, due by site day."""

import json
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from _format_eval import date_field, evaluate_expression, evaluate_rows
from _formula_grid import instants
from _node import NODE

from dbml_sharepoint.analysis.findings import FindingCode
from dbml_sharepoint.analysis.form_header import (
    HeaderRefusal,
    RenderContext,
    _date_text,
    render_header,
)
from dbml_sharepoint.analysis.formula.civil import END_DAY, FIRST_DAY, from_day_number
from dbml_sharepoint.analysis.limits import FORM_HEADER_MAX_CHARS
from dbml_sharepoint.analysis.styles import TOKENS
from dbml_sharepoint.model.conditions import Leaf
from dbml_sharepoint.model.form_tree import Bubble, HeaderTree, Row, SubtitlePart, Title

pytestmark = pytest.mark.skipif(NODE is None, reason="node is required")

SITE = "Australia/Melbourne"
BROWSERS = (SITE, "UTC", "America/Los_Angeles", "Pacific/Auckland")
IMPACTS = ("Low", "Medium", "High", "Critical")
RISKS = ("Low", "Medium", "High")
DAYS = {"Low": 14, "Medium": 21, "High": 30, "Critical": 28}
MONTHS = {"Low": 3, "Medium": 6, "High": 12}
RANK = 'IF([Impact]="Low",1,IF([Impact]="Medium",2,IF([Impact]="High",3,4)))'
TYPES = {
    "Title": "nvarchar",
    "Created": "datetime",
    "Completed": "date",
    "Impact": "impact",
    "Risk": "risk",
    "Deadline": "calculated_date",
    "Review": "calculated_date",
    "Wait": "calculated_number",
    "Chained": "calculated_date",
    "Plain": "calculated_text",
}
FORMULAS = {
    "Deadline": f"[Created]+CHOOSE({RANK},14,21,30,28)",
    "Review": (
        'IF(ISBLANK([Completed]),"",DATE(YEAR([Completed]),MONTH([Completed])'
        '+CHOOSE(IF([Risk]="Low",1,IF([Risk]="Medium",2,3)),3,6,12),DAY([Completed])))'
    ),
    "Wait": 'IF([Impact]="Critical",28,IF([Impact]="High",30,14))',
    "Chained": "[Created]+[Wait]",
    "Plain": '"x"',
}
CHOICES = {"Impact": IMPACTS, "Risk": RISKS}
WAIT = {"Critical": 28, "High": 30}
NOW = "2026-10-20T12:00:00Z"
Row_ = dict[str, object]


def _at(node: object, *path: str | int) -> object:
    for step in path:
        if isinstance(step, int):
            assert isinstance(node, list)
            node = node[step]
        else:
            assert isinstance(node, dict)
            node = node[step]
    return node


def _str(node: object, *path: str | int) -> str:
    found = _at(node, *path)
    assert isinstance(found, str)
    return found


def _ctx(formulas: dict[str, str] | None = None, zone: str = SITE) -> RenderContext:
    return RenderContext("Task", TYPES, formulas or FORMULAS, CHOICES, zone)


def _bubble(item: Bubble, formulas: dict[str, str] | None = None, zone: str = SITE) -> object:
    header = render_header(HeaderTree(rows=(Row((item,)),)), _ctx(formulas, zone))
    return _at(header, "children", 0, "children", 0)


def _ms(moment: datetime) -> dict[str, int | None]:
    return date_field(int(moment.timestamp() * 1000))


def _created(row: Row_) -> datetime:
    ms = _at(row["Created"], "epoch_ms")
    assert isinstance(ms, int)
    return datetime.fromtimestamp(ms / 1000, UTC)


def _day(moment: datetime, zone: str = SITE) -> date:
    return moment.astimezone(ZoneInfo(zone)).date()


def _text(day: date, order: str) -> str:
    parts = {"d": day.day, "m": day.month, "y": day.year}
    return "/".join(str(parts[c]) for c in order)


def _eval(
    node: object, key: str, rows: list[Row_], browser: str, now: str = NOW
) -> list[object]:
    group = "style" if key == "display" else "attributes"
    return evaluate_rows(_str(node, group, key), rows, browser_tz=browser, now=now)


def _span_text(node: object) -> str:
    return _str(node, "txtContent")


def _rows() -> list[Row_]:
    return [{"Created": _ms(m), "Impact": impact} for m in instants(SITE) for impact in IMPACTS]


# --- the written date ---------------------------------------------------------------------------


@pytest.mark.parametrize("order", ["dmy", "mdy", "ymd"])
def test_every_day_of_the_range_is_written_in_the_order_without_padding(order: str) -> None:
    expr = "=" + _date_text("[$N]", order)
    days = range(FIRST_DAY, END_DAY)
    got = evaluate_rows(expr, [{"N": n} for n in days], browser_tz="UTC", now=NOW)
    assert got == [_text(from_day_number(n), order) for n in days]


@pytest.mark.parametrize("order", ["dmy", "mdy", "ymd"])
def test_month_ends_leap_day_and_year_ends_read_back(order: str) -> None:
    pinned = [
        date(2024, 2, 29), date(2025, 2, 28), date(2026, 1, 31), date(2026, 12, 31),
        date(2027, 1, 1), date(2026, 4, 30), date(2026, 3, 1), date(2099, 12, 31),
    ]
    expr = "=" + _date_text("[$N]", order)
    rows = [{"N": (d - date(1970, 1, 1)).days} for d in pinned]
    got = evaluate_rows(expr, rows, browser_tz="UTC", now=NOW)
    assert got == [_text(d, order) for d in pinned]
    assert _text(date(2024, 2, 29), "dmy") == "29/2/2024"


# --- the inlined formula ------------------------------------------------------------------------


@pytest.mark.parametrize("order", ["dmy", "mdy", "ymd"])
@pytest.mark.parametrize("browser", BROWSERS)
def test_a_deadline_from_created_and_an_impact_choice_shows_its_date(
    order: str, browser: str
) -> None:
    bubble = _bubble(Bubble("Deadline", date_order=order))
    rows = _rows()
    got = evaluate_rows(_span_text(bubble), rows, browser_tz=browser, now=NOW)
    want = [_text(_day(_created(r)) + timedelta(days=DAYS[str(r["Impact"])]), order) for r in rows]
    assert got == want


def test_the_header_never_reads_the_calculated_column() -> None:
    row = Row((Bubble("Deadline", date_order="dmy", due=True),), Leaf("Deadline", "is_not_null"))
    header = render_header(HeaderTree(rows=(row,)), _ctx())
    assert "[$Deadline" not in json.dumps(header)


NOWS = (
    "2026-10-20T12:00:00Z", "2026-04-04T12:59:59Z", "2026-04-04T13:00:00Z",
    "2026-04-05T12:59:59Z", "2026-04-05T13:00:00Z", "2026-10-03T12:59:59Z",
    "2026-10-03T13:00:00Z", "2026-10-04T12:59:59Z", "2026-10-04T13:00:00Z",
)


@pytest.mark.parametrize("zone", [SITE, "America/Los_Angeles"])
def test_the_overdue_colour_turns_at_the_site_midnight_in_every_browser_zone(zone: str) -> None:
    bubble = _bubble(Bubble("Deadline", date_order="dmy", due=True, label="Due"), zone=zone)
    rows = [r for r in _rows() if datetime(2026, 1, 1, tzinfo=UTC) < _created(r)
            < datetime(2026, 11, 1, tzinfo=UTC)]
    blocked = TOKENS["blocked"].classes
    for now in NOWS:
        today = _day(datetime.fromisoformat(now), zone)
        for browser in BROWSERS:
            classes = _eval(bubble, "class", rows, browser, now)
            shown = _eval(bubble, "display", rows, browser, now)
            for row, cls, disp in zip(rows, classes, shown, strict=True):
                due = _day(_created(row), zone) + timedelta(days=DAYS[str(row["Impact"])])
                assert disp == "inline-block"
                assert str(cls).startswith(blocked) is (today > due), (now, browser, row)


def test_only_the_day_after_the_due_day_is_overdue() -> None:
    bubble = _bubble(Bubble("Deadline", date_order="dmy", due=True))
    created = datetime(2026, 10, 6, 12, tzinfo=ZoneInfo(SITE))  # plus 14 days is 20 October
    row = {"Created": _ms(created), "Impact": "Low"}
    blocked = TOKENS["blocked"].classes
    for now, over in (
        ("2026-10-20T12:59:59Z", False),  # 23:59:59 on the 20th, site time
        ("2026-10-20T13:00:00Z", True),  # 00:00:00 on the 21st
        ("2026-10-19T13:00:00Z", False),
    ):
        expr = _str(bubble, "attributes", "class")
        got = evaluate_expression(expr, row, browser_tz="UTC", now=now)
        assert str(got).startswith(blocked) is over, now


def test_a_review_date_from_a_stored_date_plus_months_by_a_risk_score() -> None:
    bubble = _bubble(Bubble("Review", date_order="ymd"))
    tz = ZoneInfo(SITE)
    cases: list[tuple[Row_, str]] = []
    for done in (date(2026, 1, 31), date(2026, 8, 31), date(2024, 2, 29), date(2026, 12, 31),
                 date(2026, 5, 15), date(2025, 10, 31)):
        for risk in RISKS:
            month = done.month + MONTHS[risk]
            # A month overflow carries into the next month, as DATE does (measured).
            year, month = done.year + (month - 1) // 12, (month - 1) % 12 + 1
            want = date(year, month, 1) + timedelta(days=done.day - 1)
            at = datetime(done.year, done.month, done.day, tzinfo=tz)
            cases.append(({"Completed": _ms(at), "Risk": risk}, _text(want, "ymd")))
    rows: list[Row_] = [*(r for r, _ in cases), {"Completed": date_field(None), "Risk": "Low"}]
    for browser in BROWSERS:
        got = evaluate_rows(_span_text(bubble), rows, browser_tz=browser, now=NOW)
        assert got[:-1] == [w for _, w in cases]
        shown = _eval(bubble, "display", rows, browser)
        assert shown[-1] == "none"
        assert set(shown[:-1]) == {"inline-block"}


def test_a_chained_column_feeding_a_date_column() -> None:
    bubble = _bubble(Bubble("Chained", date_order="mdy"))
    rows = _rows()
    for browser in ("UTC", SITE):
        got = evaluate_rows(_span_text(bubble), rows, browser_tz=browser, now=NOW)
        want = [
            _text(_day(_created(r)) + timedelta(days=WAIT.get(str(r["Impact"]), 14)), "mdy")
            for r in rows
        ]
        assert got == want


def test_a_blank_calculated_date_is_blank_in_a_when() -> None:
    tree = HeaderTree(rows=(Row((Bubble("Plain"),), Leaf("Review", "is_null")),))
    row = _at(render_header(tree, _ctx()), "children", 0)
    blank = {"Completed": date_field(None), "Risk": "Low"}
    filled = {"Completed": _ms(datetime(2026, 1, 1, tzinfo=UTC)), "Risk": "Low"}
    display = _str(row, "style", "display")
    for browser in BROWSERS:
        assert evaluate_expression(display, blank, browser_tz=browser, now=NOW) == "flex"
        assert evaluate_expression(display, filled, browser_tz=browser, now=NOW) == "none"


# --- refusals ------------------------------------------------------------------------------------


def _refused(item: Bubble | HeaderTree, formulas: dict[str, str] | None = None) -> HeaderRefusal:
    tree = HeaderTree(rows=(Row((item,)),)) if isinstance(item, Bubble) else item
    with pytest.raises(HeaderRefusal) as found:
        render_header(tree, _ctx(formulas))
    return found.value


def test_a_displayed_calculated_date_without_a_date_order_is_refused_naming_the_column() -> None:
    refusal = _refused(Bubble("Deadline"))
    assert refusal.finding.code is FindingCode.FORM_HEADER_DATE_ORDER_NEEDED
    assert "Task.Deadline" in refusal.finding.message


def test_only_a_bubble_can_show_a_calculated_date() -> None:
    refusal = _refused(HeaderTree(title=Title("Review", "none")))
    assert refusal.finding.code is FindingCode.FORM_HEADER_DATE_ORDER_NEEDED
    refusal = _refused(HeaderTree(subtitle=(SubtitlePart(column="Deadline"),)))
    assert refusal.finding.code is FindingCode.FORM_HEADER_DATE_ORDER_NEEDED


@pytest.mark.parametrize("column", ["Completed", "Plain", "Title"])
def test_a_date_order_on_any_other_column_is_refused(column: str) -> None:
    refusal = _refused(Bubble(column, date_order="dmy"))
    assert refusal.finding.code is FindingCode.FORM_HEADER_DATE_ORDER_UNUSED
    assert f"Task.{column}" in refusal.finding.message


def test_a_calculated_date_over_an_unguarded_stored_date_is_refused_naming_the_column() -> None:
    refusal = _refused(Bubble("Review", date_order="dmy"), {**FORMULAS, "Review": "[Completed]+1"})
    assert refusal.finding.code is FindingCode.FORM_FORMULA_COLUMN_UNSUPPORTED
    assert "Completed" in refusal.finding.message
    assert "Task.Review" in refusal.finding.message


def test_an_untranslatable_formula_names_the_formula_part() -> None:
    formulas = {**FORMULAS, "Deadline": "[Created]+LEN([Title])"}
    refusal = _refused(Bubble("Deadline", date_order="dmy"), formulas)
    assert refusal.finding.code is FindingCode.FORM_FORMULA_FUNCTION_UNSUPPORTED
    assert "LEN" in refusal.finding.message
    assert "[Created]+LEN([Title])" in refusal.finding.message


def test_a_calculated_date_and_time_result_is_refused() -> None:
    refusal = _refused(Bubble("Deadline", date_order="dmy"), {**FORMULAS, "Deadline": "[Created]"})
    assert refusal.finding.code is FindingCode.FORM_FORMULA_RESULT_UNSUPPORTED


def test_a_calculated_number_as_bubble_text_is_still_refused() -> None:
    refusal = _refused(Bubble("Wait"))
    assert refusal.finding.code is FindingCode.FORM_FORMULA_RESULT_UNSUPPORTED
    assert "Task.Wait" in refusal.finding.message


def test_a_calculated_date_compared_in_a_condition_is_refused() -> None:
    tree = HeaderTree(rows=(Row((Bubble("Plain"),), Leaf("Deadline", "eq", "2026-01-01")),))
    refusal = _refused(tree)
    assert refusal.finding.code is FindingCode.FORM_FORMULA_RESULT_UNSUPPORTED
    assert "Task.Deadline" in refusal.finding.message


def test_the_date_headers_stay_under_the_size_budget() -> None:
    for name, order in (("Deadline", "dmy"), ("Review", "mdy"), ("Chained", "ymd")):
        header = render_header(
            HeaderTree(rows=(Row((Bubble(name, date_order=order, due=True),)),)), _ctx()
        )
        size = len(json.dumps(header, separators=(",", ":")))
        print(f"SIZE {name} {size}")  # noqa: T201
        assert size <= FORM_HEADER_MAX_CHARS


def test_hide_values_and_tokens_compare_the_written_date() -> None:
    item = Bubble(
        "Deadline", date_order="dmy", hide_values=("20/10/2026",),
        tokens={"21/10/2026": "severe", "default": "good"},
    )
    bubble = _bubble(item)
    tz = ZoneInfo(SITE)
    rows: list[Row_] = [
        {"Created": _ms(datetime(2026, 10, d, 12, tzinfo=tz)), "Impact": "Low"} for d in (6, 7, 8)
    ]
    for browser in BROWSERS:
        assert _eval(bubble, "display", rows, browser) == ["none", "inline-block", "inline-block"]
        classes = _eval(bubble, "class", rows, browser)
        assert str(classes[1]).startswith(TOKENS["severe"].classes)
        assert str(classes[2]).startswith(TOKENS["good"].classes)


@pytest.mark.parametrize("name", sorted(FORMULAS))
def test_no_rendered_header_reads_any_calculated_column(name: str) -> None:
    if name == "Wait":
        row = Row((Bubble("Plain"),), Leaf("Wait", "gt", 20))
    elif TYPES[name] == "calculated_date":
        row = Row((Bubble(name, date_order="ymd", due=True),), Leaf(name, "is_not_null"))
    else:
        row = Row((Bubble(name),), Leaf(name, "eq", "x"))
    text = json.dumps(render_header(HeaderTree(rows=(row,)), _ctx()))
    assert f"[${name}" not in text


def test_two_review_bubbles_overflow_the_budget_naming_the_column() -> None:
    both = (Bubble("Review", date_order="dmy"), Bubble("Review", date_order="mdy"))
    refusal = _refused(HeaderTree(rows=(Row(both),)))
    assert refusal.finding.code is FindingCode.FORM_HEADER_TOO_LARGE
    assert "Task.Review" in refusal.finding.message
