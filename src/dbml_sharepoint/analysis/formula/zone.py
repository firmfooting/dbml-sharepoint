"""The site zone as formatting-expression arithmetic, for date formulas.

A header cannot ask the formatting language for the site's clock: its date functions read the
browser's zone. So a date is a whole-day number (days since 1970-01-01 on the site's calendar), and
the only two places a zone enters are turning an instant into that day (a system date column) and
turning a day back into the instant of site-local midnight (a date result). Both use plain
arithmetic on epoch milliseconds, which does not depend on the browser's zone.

The offsets and the daylight rule are read from `analysis.timezones.zone_table`. They are encoded
only when the zone is one fixed offset or two offsets switched on "nth or last weekday of a month
at a wall time", and only for the years over which that rule is verified; the caller blanks
anything outside them.

Every function used below is on the formatting syntax reference (Microsoft Learn,
https://learn.microsoft.com/en-us/sharepoint/dev/declarative-customization/formatting-syntax-reference):
floor, the arithmetic operators including `%`, the comparison and `&&` / `||` operators, `if`,
`Date()` (strings or numbers to a date) and `Number(Date(..))` (milliseconds since 1970).
"""

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta
from functools import cache

from dbml_sharepoint.analysis.findings import FindingCode
from dbml_sharepoint.analysis.formula.refusal import FormulaRefusal
from dbml_sharepoint.analysis.timezones import WINDOW_START, zone_table

_EPOCH_ORDINAL = date(1970, 1, 1).toordinal()
_MS_DAY = 86_400_000
_MS_MINUTE = 60_000
# Days since 1970-01-01 of 1996-03-01, the start of a four-year group that ends on a leap day.
_GROUP_START = 9556
# 365.2425 days in milliseconds; a year estimate off by a day near new year is harmless because no
# accepted rule switches within a month of it.
_MEAN_YEAR_MS = 31_556_952_000
# A day expression longer than this is looked up in a per-day string rather than compared.
_BITMAP_FROM = 2000
_FIRST_WINDOW_YEAR = WINDOW_START.year
_LAST_YEAR = 2049
# A date before the verified span reads blank, so the span must reach back over the years a form
# plausibly holds; a rule that changed later than this is refused.
_LATEST_FIRST_YEAR = 2010


@dataclass(frozen=True, slots=True)
class Switch:
    """One change of offset: the `nth` (1 to 4, or -1 for the last) `weekday` (0 is Sunday)."""

    month: int
    nth: int
    weekday: int
    minute: int  # wall-clock minutes after midnight, on the clock before the change


@dataclass(frozen=True, slots=True)
class ZoneRule:
    name: str
    standard: int  # minutes east of UTC
    daylight: int | None
    switches: tuple[Switch, Switch] | None  # (to daylight, to standard); None without daylight
    first_year: int  # the verified span, first and last year inclusive
    last_year: int

    @property
    def northern(self) -> bool:
        return self.switches is not None and self.switches[0].month < self.switches[1].month


def _refuse(name: str, why: str) -> FormulaRefusal:
    return FormulaRefusal(
        FindingCode.FORM_FORMULA_ZONE_UNSUPPORTED,
        f"needs the site zone {name}, whose offsets {why}",
    )


type _Candidates = set[tuple[int, int, int, int]]  # (month, nth, weekday, minute)


def _candidates(wall_day: int, month: int, year: int, weekday: int, minute: int) -> _Candidates:
    found = {(month, (wall_day - 1) // 7 + 1, weekday, minute)}
    if wall_day + 7 > monthrange(year, month)[1]:
        found.add((month, -1, weekday, minute))
    return found


def _changes(name: str, daylight: bool) -> dict[int, list[tuple[bool, int, _Candidates]]]:
    """Each wall-clock year's offset changes: (goes up, offset after, weekday-rule candidates)."""
    changes: dict[int, list[tuple[bool, int, _Candidates]]] = {}
    table = zone_table(name)
    before = table.start_offset
    for at, after in table.transitions:
        wall = at + timedelta(minutes=before)
        minute = wall.hour * 60 + wall.minute
        guess = _candidates(wall.day, wall.month, wall.year, (wall.weekday() + 1) % 7, minute)
        changes.setdefault(wall.year, []).append((after > before, after, guess))
        if daylight and not 2 <= wall.month <= 11:
            raise _refuse(name, "switch within a month of new year")
        # A skipped midnight needs a forward switch at 00:00; a repeated one a backward switch
        # within its own size of 00:00.
        if daylight and minute <= (0 if after > before else before - after):
            raise _refuse(name, "switch near midnight, where a local midnight can be skipped")
        before = after
    return changes


@cache
def zone_rule(name: str) -> ZoneRule:
    """The zone's current offsets and the rule that selects between them, or a refusal."""
    table = zone_table(name)
    offsets = table.current_offsets
    if len(offsets) > 2:
        raise _refuse(name, "number more than two")
    changes = _changes(name, len(offsets) == 2)
    if len(offsets) == 1:
        last = max(changes, default=_FIRST_WINDOW_YEAR - 1)
        first = max(last + 1, _FIRST_WINDOW_YEAR)
        return _checked(ZoneRule(name, offsets[0], None, None, first, _LAST_YEAR))
    standard, daylight = offsets
    rule: dict[bool, _Candidates | None] = {True: None, False: None}
    first = _LAST_YEAR + 1
    for year in range(_LAST_YEAR, _FIRST_WINDOW_YEAR - 1, -1):
        year_changes = changes.get(year, [])
        ups = [c for c in year_changes if c[0]]
        downs = [c for c in year_changes if not c[0]]
        if len(year_changes) != 2 or len(ups) != 1 or len(downs) != 1:
            break
        if ups[0][1] != daylight or downs[0][1] != standard:
            break
        merged = {
            up: ((rule[up] or c[2]) & c[2]) for up, c in ((True, ups[0]), (False, downs[0]))
        }
        if not all(merged.values()):
            break
        rule = dict(merged)
        first = year
    if first > _LAST_YEAR or not (found_up := rule[True]) or not (found_down := rule[False]):
        raise _refuse(name, "follow no weekday rule over the years the table covers")
    return _checked(
        ZoneRule(name, standard, daylight, (_pick(found_up), _pick(found_down)), first, _LAST_YEAR)
    )


def _pick(found: _Candidates) -> Switch:
    # A day can be both the fourth and the last of its weekday; either selects it in every year.
    month, nth, weekday, minute = min(found, key=lambda c: (c[1] != -1, c[1]))
    return Switch(month, nth, weekday, minute)


def _checked(rule: ZoneRule) -> ZoneRule:
    if rule.first_year > _LATEST_FIRST_YEAR:
        raise _refuse(
            rule.name,
            f"follow one rule only from {rule.first_year}, too recently for the dates a form holds",
        )
    return rule


def days_of(year: str, month: str, day: str) -> str:
    """Days since 1970-01-01 of a calendar date; month and day overflow carry over."""
    # March-based so the leap day is last; years 1901 to 2099 only (no century rule), which the
    # span guard enforces.
    t = f"(12 * ({year}) + ({month}) - 3)"
    return (
        f"(365 * floor({t} / 12) + floor({t} / 48) + floor((153 * ({t} % 12) + 2) / 5)"
        f" + ({day}) - 719484)"
    )


def parts_of(days: str) -> tuple[str, str, str]:
    """Expressions for the year, month and day of a day number (valid inside the span guard)."""
    j = f"(({days}) - {_GROUP_START})"
    k = f"floor((4 * {j} + 3) / 1461)"  # whole March-based years since 1996-03-01
    doy = f"({j} - 365 * {k} - floor({k} / 4))"
    mp = f"floor((5 * {doy} + 2) / 153)"  # months since March
    year = f"(1996 + {k} + floor({mp} / 10))"
    month = f"(({mp} + 2) % 12 + 1)"
    day = f"({doy} - floor((153 * {mp} + 2) / 5) + 1)"
    return year, month, day


def _switch_day(year: int, sw: Switch) -> int:
    """Day number of the switch in `year`, by the rule the zone was verified against."""
    first = date(year, sw.month, 1)
    first_weekday = (first.weekday() + 1) % 7  # 0 is Sunday
    if sw.nth > 0:
        dom = 1 + (sw.weekday - first_weekday) % 7 + 7 * (sw.nth - 1)
    else:
        size = monthrange(year, sw.month)[1]
        last_weekday = (first_weekday + size - 1) % 7
        dom = size - (last_weekday - sw.weekday) % 7
    return first.toordinal() - _EPOCH_ORDINAL + dom - 1


def _switch_days(index: str, rule: ZoneRule, switches: tuple[Switch, Switch]) -> tuple[str, str]:
    """Expressions for the two switch day numbers of the year at `index` in the verified span.

    Each is looked up in a five-digit-per-year table (Learn: substring and Number()), so the
    weekday rule is applied here in Python and the expression stays short.
    """
    found = []
    for sw in switches:
        digits = "".join(
            f"{_switch_day(y, sw):05d}" for y in range(rule.first_year, rule.last_year + 1)
        )
        found.append(f"Number(substring('{digits}', 5 * {index}, 5 * {index} + 5))")
    return found[0], found[1]


def _dst_condition(rule: ZoneRule, *, after: str, before: str) -> str:
    # Between the two switches in a northern year, outside them in a southern one.
    joiner = " && " if rule.northern else " || "
    return f"({after}{joiner}{before})"


def _span_days(year: int, month: int) -> int:
    return date(year, month, 1).toordinal() - _EPOCH_ORDINAL


def _outside(value: str, low: int, high: int) -> str:
    # One reference to `value`: the quotient is 0 only inside [low, high).
    return f"(floor((({value}) - {low}) / {high - low}) != 0)"


def out_of_span_day(days: str, rule: ZoneRule) -> str:
    """True when a day number is outside the years the zone's rule is verified for."""
    return _outside(days, _span_days(rule.first_year, 1), _span_days(rule.last_year + 1, 1))


def out_of_span_instant(ms: str, rule: ZoneRule) -> str:
    """True when an instant is within a day of, or outside, the verified years."""
    low = (_span_days(rule.first_year, 1) + 1) * _MS_DAY
    return _outside(ms, low, (_span_days(rule.last_year + 1, 1) - 1) * _MS_DAY)


def _daylight_at_midnight(days: str, rule: ZoneRule, switches: tuple[Switch, Switch]) -> str:
    index = f"floor(({days}) / 365.2425 + {1970 - rule.first_year})"
    up, down = _switch_days(index, rule, switches)
    # A switch happens after midnight, so midnight of the switch day is still the old state.
    return _dst_condition(rule, after=f"({days}) > {up}", before=f"({days}) <= {down}")


def _daylight_bitmap(rule: ZoneRule, switches: tuple[Switch, Switch]) -> str:
    """One character per day of the verified span: 1 when midnight of that day is in daylight."""
    flags = []
    for year in range(rule.first_year, rule.last_year + 1):
        up, down = (_switch_day(year, sw) for sw in switches)
        first = _span_days(year, 1)
        for day in range(first, _span_days(year + 1, 1)):
            inside = up < day <= down if rule.northern else (day > up or day <= down)
            flags.append("1" if inside else "0")
    return "".join(flags)


def midnight_ms(days: str, rule: ZoneRule) -> str:
    """Epoch milliseconds of site-local midnight starting day number `days`."""
    if rule.daylight is None or rule.switches is None:
        return f"(({days}) * {_MS_DAY} - {rule.standard * _MS_MINUTE})"
    if len(days) > _BITMAP_FROM:
        # A long day expression is referenced once per lookup, so the lookup that names it least
        # often wins even though its string is long.
        start = _span_days(rule.first_year, 1)
        index = f"(({days}) - {start})"
        flag = f"substring('{_daylight_bitmap(rule, rule.switches)}', {index}, {index} + 1) == '1'"
    else:
        flag = _daylight_at_midnight(days, rule, rule.switches)
    return (
        f"(({days}) * {_MS_DAY} - if({flag}, {rule.daylight * _MS_MINUTE}, "
        f"{rule.standard * _MS_MINUTE}))"
    )


def day_of_instant(ms: str, rule: ZoneRule) -> str:
    """Day number on the site's calendar of the epoch-millisecond instant `ms`."""
    std = rule.standard * _MS_MINUTE
    if rule.daylight is None or rule.switches is None:
        return f"floor((({ms}) + {std}) / {_MS_DAY})"
    to_daylight, to_standard = rule.switches
    dst = rule.daylight * _MS_MINUTE
    index = f"floor((({ms}) + {std}) / {_MEAN_YEAR_MS} + {1970 - rule.first_year})"
    up_day, down_day = _switch_days(index, rule, rule.switches)
    up_at = f"{up_day} * {_MS_DAY} + {to_daylight.minute * _MS_MINUTE} - {std}"
    down_at = f"{down_day} * {_MS_DAY} + {to_standard.minute * _MS_MINUTE} - {dst}"
    flag = _dst_condition(rule, after=f"({ms}) >= ({up_at})", before=f"({ms}) < ({down_at})")
    return f"floor((({ms}) + if({flag}, {dst}, {std})) / {_MS_DAY})"


def local_midnight(year: str, month: str, day: str, rule: ZoneRule) -> str:
    """The instant of site-local midnight on a date, or '' when it is outside the verified years."""
    days = days_of(year, month, day)
    return f"if({out_of_span_day(days, rule)}, '', Date({midnight_ms(days, rule)}))"
