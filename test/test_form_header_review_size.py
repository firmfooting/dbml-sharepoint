"""A review-due header whose month count comes from a rating CHOOSE: size, and the date it shows.

The formulas are generic: a rating from two five-step choices, then the same day some months on,
clamped to the end of that month, with the months chosen by the rating and a result.
"""

import json
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest
from _format_eval import date_field, evaluate_rows
from _formula_grid import check_parity

from dbml_sharepoint.analysis.form_header import RenderContext, render_header
from dbml_sharepoint.analysis.formula.syntax import ColumnKind
from dbml_sharepoint.analysis.formula.translate import TranslationContext, translate_column
from dbml_sharepoint.analysis.styles import TOKENS
from dbml_sharepoint.model.form_tree import Bubble, HeaderTree, Row
from dbml_sharepoint.testing.node import NODE

pytestmark = pytest.mark.skipif(NODE is None, reason="node is required")

SITE = "Australia/Melbourne"
LIKELIHOOD = ("Rare", "Unlikely", "Likely", "Very Likely", "Almost Certain")
CONSEQUENCE = ("Minor", "Moderate", "Substantial", "Major", "Severe")
OPTIONS = [
    "Low", "Low", "Low", "Medium", "Medium",
    "Low", "Low", "Medium", "Medium", "High",
    "Low", "Medium", "Medium", "High", "High",
    "Medium", "Medium", "High", "High", "Extreme",
    "Medium", "High", "High", "Extreme", "Extreme",
]
RATING = (
    'IF(OR(ISBLANK([Likelihood]),ISBLANK([Consequence])),"",CHOOSE('
    '(IF([Likelihood]="Rare",1,IF([Likelihood]="Unlikely",2,IF([Likelihood]="Likely",3,'
    'IF([Likelihood]="Very Likely",4,5))))-1)*5+IF([Consequence]="Minor",1,'
    'IF([Consequence]="Moderate",2,IF([Consequence]="Substantial",3,'
    'IF([Consequence]="Major",4,5)))),'
    + ",".join(f'"{o}"' for o in OPTIONS)
    + "))"
)
MONTHS = (
    'IF([Result]="Non-compliant",IF([Rating]="Low",12,IF([Rating]="Medium",6,3)),36)'
)
REVIEW = (
    'IF(OR([Kind]="REG",NOT(ISBLANK([Superseded])),[State]<>"Complete",ISBLANK([Done]),'
    'ISBLANK([Result])),"",MIN(DATE(YEAR([Done]),MONTH([Done])+' + MONTHS + ",DAY([Done])),"
    "DATE(YEAR([Done]),MONTH([Done])+" + MONTHS + "+1,1)-1))"
)
TYPES = {
    "Kind": "nvarchar", "State": "nvarchar", "Superseded": "date", "Done": "date",
    "Result": "nvarchar", "Likelihood": "nvarchar", "Consequence": "nvarchar",
    "Rating": "calculated_text", "Review": "calculated_date",
}
CHOICES = {
    "State": ("Complete", "Open"), "Result": ("Compliant", "Non-compliant"),
    "Likelihood": LIKELIHOOD, "Consequence": CONSEQUENCE,
}
FORMULAS = {"Rating": RATING, "Review": REVIEW}
# A 31st into a short, a 30-day and a leap February, a December rollover and a 29 February.
STARTS = (
    date(2025, 8, 31), date(2023, 8, 31), date(2025, 11, 30), date(2025, 12, 31),
    date(2025, 10, 15), date(2024, 2, 29), date(2027, 12, 31),
)
NOW = "2026-10-20T12:00:00Z"


def _rating(likelihood: str | None, consequence: str | None) -> str:
    if likelihood not in LIKELIHOOD or consequence not in CONSEQUENCE:
        return ""
    return OPTIONS[LIKELIHOOD.index(likelihood) * 5 + CONSEQUENCE.index(consequence)]


def _review(start: date, result: str, rating: str) -> str:
    months = {"Low": 12, "Medium": 6}.get(rating, 3) if result == "Non-compliant" else 36
    index = start.year * 12 + start.month - 1 + months
    year, month = divmod(index, 12)
    last = (date(year + (month + 1) // 12, (month + 1) % 12 + 1, 1) - date(year, month + 1, 1)).days
    return f"{min(start.day, last)}/{month + 1}/{year}"


def _header() -> dict[str, object]:
    ctx = RenderContext("Task", TYPES, FORMULAS, CHOICES, SITE)
    item = Bubble("Review", date_order="dmy", due=True)
    return render_header(HeaderTree(rows=(Row((item,)),)), ctx)


def _dict(node: object) -> dict[str, object]:
    assert isinstance(node, dict)
    return node


def _list(node: object) -> list[object]:
    assert isinstance(node, list)
    return node


def _bubble() -> dict[str, object]:
    row = _dict(_list(_header()["children"])[0])
    return _dict(_list(row["children"])[0])


def _display() -> str:
    shown = _dict(_bubble()["style"])["display"]
    assert isinstance(shown, str)
    return shown


def _field(day: date) -> dict[str, int | None]:
    midnight = datetime(day.year, day.month, day.day, tzinfo=ZoneInfo(SITE))
    return date_field(int(midnight.timestamp() * 1000))


def _row(
    start: date, result: str, likelihood: str | None, consequence: str | None
) -> dict[str, object]:
    return {
        "Kind": "Item", "State": "Complete", "Superseded": date_field(None), "Done": _field(start),
        "Result": result, "Likelihood": likelihood or "", "Consequence": consequence or "",
        "Done.displayValue": "x", "Superseded.displayValue": "",
    }


def test_the_header_fits_well_inside_the_budget() -> None:
    assert len(json.dumps(_header(), separators=(",", ":"))) < 400_000


def test_the_rating_choose_agrees_with_the_reference_over_every_pair_and_blank() -> None:
    kinds: dict[str, ColumnKind] = dict.fromkeys(CHOICES, "choice")
    ctx = TranslationContext({"Rating": RATING}, kinds, {"Rating": "text"}, CHOICES, SITE)
    expression = translate_column("Rating", ctx).expression
    check_parity(RATING, expression, {"Rating": RATING}, kinds, CHOICES, (SITE, "UTC"))
    pairs = [(a, b) for a in LIKELIHOOD for b in CONSEQUENCE] + [(None, "Minor"), ("Rare", None)]
    rows: list[dict[str, object]] = [
        {"Likelihood": a or "", "Consequence": b or ""} for a, b in pairs
    ]
    got = evaluate_rows(expression, rows, browser_tz="UTC", now=NOW)
    assert got == [_rating(a, b) for a, b in pairs]


@pytest.mark.parametrize("result", ["Compliant", "Non-compliant"])
def test_the_review_date_is_the_same_day_months_on_or_the_months_last_day(result: str) -> None:
    bubble = _bubble()
    combos = [(a, b) for a in (*LIKELIHOOD, None) for b in (*CONSEQUENCE, None)]
    cases = [(s, a, b) for s in STARTS for a, b in combos]
    rows = [_row(s, result, a, b) for s, a, b in cases]
    text = bubble["txtContent"]
    display = _display()
    assert isinstance(text, str)
    for browser in (SITE, "America/Los_Angeles"):
        shown = evaluate_rows(text, rows, browser_tz=browser, now=NOW)
        hidden = evaluate_rows(display, rows, browser_tz=browser, now=NOW)
        assert hidden == ["inline-block"] * len(rows)
        assert shown == [_review(s, result, _rating(a, b)) for s, a, b in cases]


def test_a_row_the_formula_leaves_blank_hides_the_bubble() -> None:
    display = _display()
    ok = _row(STARTS[0], "Compliant", "Rare", "Minor")
    rows = [
        {**ok, "Kind": "REG"}, {**ok, "State": "Open"}, {**ok, "Result": ""},
        {**ok, "Done": date_field(None), "Done.displayValue": ""},
        {**ok, "Superseded": _field(STARTS[0]), "Superseded.displayValue": "x"}, ok,
    ]
    got = evaluate_rows(display, rows, browser_tz=SITE, now=NOW)
    assert got == ["none"] * 5 + ["inline-block"]


def test_the_due_colour_turns_on_the_day_after_the_clamped_date() -> None:
    # 31 August plus six months is 28 February 2026, overdue from the site's next midnight.
    klass = _dict(_bubble()["attributes"])["class"]
    assert isinstance(klass, str)
    row = _row(date(2025, 8, 31), "Non-compliant", "Rare", "Major")  # a Medium rating
    overdue = TOKENS["blocked"].classes
    nows = {
        "2026-02-28T12:00:00Z": False, "2026-02-28T14:00:00Z": True, "2026-03-05T00:00:00Z": True,
    }
    for now, expected in nows.items():
        got = evaluate_rows(klass, [row], browser_tz=SITE, now=now)
        assert (overdue in str(got[0])) is expected, now
