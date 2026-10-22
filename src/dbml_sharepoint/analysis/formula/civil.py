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


_FIRST_INDEX = 12 * 1904  # month_index of 1904-03, where the formulas start
_END_INDEX = 12 * 2100  # month_index of 2100-03, the first month past them


def month_index(year: str, month: str) -> str:
    """Months since the March before year 0, the index `days_of` counts a date's month by."""
    return f"(12 * ({year}) + ({month}) - 3)"


def outside_months(index: str) -> str:
    """True when the first day of a month index falls outside the range the formulas hold in."""
    return f"(floor((({index}) - {_FIRST_INDEX}) / {_END_INDEX - _FIRST_INDEX}) != 0)"


def days_of(year: str, month: str, day: str) -> str:
    """Day number of a calendar date; month and day overflow carry over as in a spreadsheet."""
    return days_of_index(month_index(year, month), day)


def days_of_index(index: str, day: str) -> str:
    # March-based months make the leap day last in its year; 365 * q + floor(q / 4) is
    # floor(1461 * q / 4), which names the index once less.
    return (
        f"(floor(1461 * floor({index} / 12) / 4) + floor((153 * ({index} % 12) + 2) / 5)"
        f" + ({day}) - 719484)"
    )


def _march_parts(days: str) -> tuple[str, str, str]:
    j = f"(({days}) + {-FIRST_DAY})"  # FIRST_DAY is before 1970, so a negative literal is avoided
    k = f"floor((4 * {j} + 3) / 1461)"  # whole March-based years since 1904-03-01
    doy = f"({j} - floor(1461 * {k} / 4))"  # 365 * k + floor(k / 4) days precede year k
    mp = f"floor((5 * {doy} + 2) / 153)"  # months since March
    return k, doy, mp


def month_index_of(days: str) -> str:
    """`month_index` of a day number's own year and month, in fewer characters than from parts.

    The year is 1904 + k + floor(mp / 10) and the month (mp + 2) % 12 + 1, and
    12 * floor(mp / 10) + (mp + 2) % 12 is mp + 2, so the index is 12 * 1904 + 12 * k + mp.
    """
    k, _, mp = _march_parts(days)
    return f"({_FIRST_INDEX} + 12 * {k} + {mp})"


def parts_of(days: str) -> tuple[str, str, str]:
    """Expressions for the year, month and day of a day number."""
    k, doy, mp = _march_parts(days)
    year = f"(1904 + {k} + floor({mp} / 10))"
    month = f"(({mp} + 2) % 12 + 1)"
    day = f"({doy} - floor((153 * {mp} + 2) / 5) + 1)"
    return year, month, day


def clamped_parts(index: str, day: str) -> tuple[str, str, str]:
    """Year, month and day of day `day` of month `index`, or the month's last day if shorter."""
    year = f"floor(({index} + 2) / 12)"
    month = f"(({index} + 2) % 12 + 1)"
    # A March-based month m starts on floor((153 m + 2) / 5) for m up to 11, so its length is the
    # difference to the next; February (m 11) has 28 days, and 29 in a leap year (index 47 mod 48).
    length = (
        f"(if({index} % 12 == 11, 28 + if({index} % 48 == 47, 1, 0), "
        f"floor((153 * ({index} % 12) + 155) / 5) - floor((153 * ({index} % 12) + 2) / 5)))"
    )
    return year, month, f"if({day} < {length}, {day}, {length})"
