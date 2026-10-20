"""Calendar arithmetic as formatting expressions, on whole-day numbers.

A day number counts days from 1970-01-01. The formulas use only floor, `%` on non-negative values,
`+ - * /` and `if`, all on the formatting syntax reference (Microsoft Learn,
https://learn.microsoft.com/en-us/sharepoint/dev/declarative-customization/formatting-syntax-reference).
They hold from 1904-03-01 (a March that opens a leap-year group) to 2100-02-28 (before 2100,
which is not a leap year): a four-year cycle with no century rule, so callers check the range.
"""

from datetime import date

_EPOCH = date(1970, 1, 1).toordinal()
FIRST_DAY = date(1904, 3, 1).toordinal() - _EPOCH
END_DAY = date(2100, 3, 1).toordinal() - _EPOCH  # the first day past the range


def to_day_number(day: date) -> int:
    return day.toordinal() - _EPOCH


def from_day_number(days: int) -> date:
    return date.fromordinal(days + _EPOCH)


def days_of(year: str, month: str, day: str) -> str:
    """Day number of a calendar date; month and day overflow carry over as in a spreadsheet."""
    # March-based months make the leap day last in its year.
    t = f"(12 * ({year}) + ({month}) - 3)"
    return (
        f"(365 * floor({t} / 12) + floor({t} / 48) + floor((153 * ({t} % 12) + 2) / 5)"
        f" + ({day}) - 719484)"
    )


def parts_of(days: str) -> tuple[str, str, str]:
    """Expressions for the year, month and day of a day number."""
    j = f"(({days}) + {-FIRST_DAY})"  # FIRST_DAY is before 1970, so a negative literal is avoided
    k = f"floor((4 * {j} + 3) / 1461)"  # whole March-based years since 1904-03-01
    doy = f"({j} - 365 * {k} - floor({k} / 4))"
    mp = f"floor((5 * {doy} + 2) / 153)"  # months since March
    year = f"(1904 + {k} + floor({mp} / 10))"
    month = f"(({mp} + 2) % 12 + 1)"
    day = f"({doy} - floor((153 * {mp} + 2) / 5) + 1)"
    return year, month, day
