"""The reference and formatting evaluators, pinned to measured facts and documented behaviour."""

from datetime import UTC, date, datetime
from typing import cast
from zoneinfo import ZoneInfo

import pytest
from _format_eval import evaluate_expression
from _formula_facts import (
    BLANK_COERCION,
    BLANK_OPERANDS,
    CREATED_PLUS_DAYS_DAY,
    DATE_OVERFLOW,
    TEXT_EQUALITY_CASE,
)
from _formula_grid import check_parity, error_rows, grid
from _formula_reference import ERROR, ColumnError, evaluate
from _node import NODE

from dbml_sharepoint.analysis.formula.parse import parse_formula
from dbml_sharepoint.analysis.formula.syntax import ColumnKind

pytestmark = pytest.mark.skipif(NODE is None, reason="node is required")

# The operands the blank cases used. The date is a UTC instant: read in the site zone it is
# 11:00 on the 15th, which is why its serial number ends in .4583.
OPERANDS: dict[str, object] = {
    "number": float(BLANK_OPERANDS["number"]),
    "text": BLANK_OPERANDS["text"],
    "date": datetime.fromisoformat(BLANK_OPERANDS["date"]).astimezone(UTC),
    "choice": BLANK_OPERANDS["choice"],
}
CASES = [
    (op, kind, side)
    for op, (_, by_kind) in BLANK_COERCION.items()
    for kind in by_kind
    for side in ("left", "right", "both")
]


def _cell(cell: str, sign: str) -> object:
    """A measured cell as the value the reference should return."""
    if cell.startswith("error;#"):
        return ColumnError(int(cell.removeprefix("error;#")))
    if cell in ("T", "F"):
        return cell == "T"
    return cell if sign == "&" else float(cell)


def test_there_are_144_blank_cases() -> None:
    assert len(CASES) == 144


@pytest.mark.parametrize(("op", "kind", "side"), CASES, ids=["-".join(c) for c in CASES])
def test_blank_coercion_matches_the_measured_cell(op: str, kind: str, side: str) -> None:
    sign, by_kind = BLANK_COERCION[op]
    value = OPERANDS[kind]
    row = {"L": None if side != "right" else value, "R": None if side != "left" else value}
    # The sign goes between two columns of the operand's type; a blank column is None.
    result = evaluate(
        parse_formula(f"[L]{sign}[R]"), row, dict.fromkeys(row, cast("ColumnKind", kind))
    )

    expected = _cell(by_kind[kind][side], sign)
    if isinstance(expected, float):
        assert isinstance(result, float)
        assert result == pytest.approx(expected, rel=1e-12)
    else:
        assert result == expected


def test_a_column_error_carries_its_code() -> None:
    assert ERROR(1) == ColumnError(1)
    assert evaluate(parse_formula("[T]+1"), {"T": "abc"}, {"T": "text"}) == ERROR(1)


@pytest.mark.parametrize("call", list(DATE_OVERFLOW))
def test_date_overflow_gives_the_displayed_day(call: str) -> None:
    day, month, year = (int(p) for p in DATE_OVERFLOW[call]["displayed"].split("/"))
    row = {"DateLeap": date(2024, 2, 29)}

    assert evaluate(parse_formula(call), row, {"DateLeap": "date"}) == date(year, month, day)


@pytest.mark.parametrize("call", list(DATE_OVERFLOW))
def test_the_overflow_instant_is_site_local_midnight_of_the_displayed_day(call: str) -> None:
    day, month, year = (int(p) for p in DATE_OVERFLOW[call]["displayed"].split("/"))
    instant = datetime.fromisoformat(DATE_OVERFLOW[call]["instant"])
    local = instant.astimezone(ZoneInfo("Australia/Melbourne"))

    assert (local.date(), local.hour) == (date(year, month, day), 0)


def test_text_equality_ignores_case() -> None:
    kinds: dict[str, ColumnKind] = {"T": "text"}

    assert (TEXT_EQUALITY_CASE["literal"], TEXT_EQUALITY_CASE["column"]) == ("T", "T")
    assert evaluate(parse_formula('"a"="A"'), {}, kinds) is True
    assert evaluate(parse_formula('[T]="ABC"'), {"T": "abc"}, kinds) is True
    assert evaluate(parse_formula('[T]<>"ABC"'), {"T": "abc"}, kinds) is False


@pytest.mark.parametrize(("days", "shown"), [(0, "shown_zero"), (1, "shown_one")])
def test_a_system_date_plus_days_takes_its_day_in_the_site_zone(days: int, shown: str) -> None:
    created = datetime.fromisoformat(CREATED_PLUS_DAYS_DAY["created"])
    result = evaluate(parse_formula(f"[Created]+{days}"), {"Created": created}, {"Created": "date"})

    assert result == date.fromisoformat(CREATED_PLUS_DAYS_DAY[shown])
    assert created.date() != date.fromisoformat(CREATED_PLUS_DAYS_DAY["shown_zero"])


def test_a_date_plus_days_is_a_date() -> None:
    assert evaluate(parse_formula("[D]+3"), {"D": date(2026, 2, 27)}, {"D": "date"}) == date(
        2026, 3, 2
    )


def test_a_chained_column_reads_through_the_reference() -> None:
    kinds: dict[str, ColumnKind] = {"N": "number", "Double": "number"}
    check_parity("[Double]+1", "=[$N] * 2 + 1", {"Double": "[N]*2"}, kinds, {}, ("UTC",))


def test_the_grid_covers_blanks_unlisted_values_case_variants_and_month_ends() -> None:
    rows = list(grid({"S": "choice", "D": "date", "N": "number"}, {"S": ("Open", "Done")}))

    assert {r["S"] for r in rows} == {
        None,
        "Open",
        "open",
        "OPEN",
        "Done",
        "done",
        "DONE",
        "Unlisted value",
    }
    assert {r["D"] for r in rows} >= {
        None,
        date(2024, 2, 29),
        date(2026, 2, 28),
        date(2025, 12, 31),
        date(2026, 10, 20),
        date(2026, 10, 21),
    }
    assert any(r["N"] is None for r in rows)


def test_error_rows_name_the_rows_the_parity_check_skips() -> None:
    kinds: dict[str, ColumnKind] = {"T": "text"}
    skipped = error_rows("[T]+1", {}, kinds, {})

    assert skipped and all(r["T"] is not None for r in skipped)
    check_parity("[T]+1", "=[$T] + 1", {}, kinds, {}, ("UTC",))


CHOICES = {"Status": ("Open", "Done")}
STATUS_KINDS: dict[str, ColumnKind] = {"Status": "choice"}
CHECK = 'IF([Status]="Done","Yes","No")'


def test_a_right_translation_passes_the_parity_check_in_every_browser_zone() -> None:
    check_parity(
        CHECK,
        "=if(toLowerCase([$Status] + '') == 'done', 'Yes', 'No')",
        {},
        STATUS_KINDS,
        CHOICES,
        ("UTC", "Pacific/Auckland", "America/Los_Angeles"),
    )


def test_the_evaluators_catch_a_wrong_translation() -> None:
    # Formatting `==` is case-sensitive, a formula's `=` is not: this is the classic wrong port.
    with pytest.raises(AssertionError, match="differing rows"):
        check_parity(
            CHECK, "=if([$Status] == 'Done', 'Yes', 'No')", {}, STATUS_KINDS, CHOICES, ("UTC",)
        )


# Each expectation is the example the formatting syntax reference gives for the function.
# https://learn.microsoft.com/en-us/sharepoint/dev/declarative-customization/formatting-syntax-reference
@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("=toString(45)", "45"),  # Learn, Unary operators: toString
        ("=padStart('DogFood', 10, 'A')", "AAADogFood"),  # Learn, Ternary operators: padStart
        ("=padStart('DogFood', 10, 'AB')", "ABADogFood"),  # Learn, Ternary operators: padStart
        ("=padStart('DogFood', 5, 'A')", "DogFood"),  # Learn, Ternary operators: padStart
        ("=floor(45.5)", 45),  # Learn, Unary operators: floor
        ("=abs(-45)", 45),  # Learn, Unary operators: abs
        ("=pow(2,3)", 8),  # Learn, Binary operators: pow
        ("=toLowerCase('DogFood')", "dogfood"),  # Learn, Unary operators: toLowerCase
        ("=addDays(Date('11/14/2021'), 3)", "2021-11-17T00:00:00.000Z"),  # Learn: addDays
        ("=addDays(Date('11/14/2021'), -1)", "2021-11-13T00:00:00.000Z"),  # Learn: addDays
    ],
)
def test_the_formatting_functions_give_what_learn_documents(
    expression: str, expected: object
) -> None:
    got = evaluate_expression(expression, {}, browser_tz="UTC", now="2026-10-20T12:00:00Z")

    assert got == expected


def test_a_field_reads_from_the_row_and_the_browser_zone_applies() -> None:
    row = {"Due": "2026-10-19T13:00:00Z"}
    expression = "=getDate(Date([$Due]))"

    assert evaluate_expression(expression, row, browser_tz="UTC", now="2026-10-20T00:00:00Z") == 19
    assert (
        evaluate_expression(
            expression, row, browser_tz="Australia/Melbourne", now="2026-10-20T00:00:00Z"
        )
        == 20
    )
