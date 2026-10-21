"""The site zone's offsets and daylight rule, read from the zone table.

A zone is accepted when it is one fixed offset, or two offsets switched on "nth or last weekday of
a month at a wall time", and only over the years the rule is verified for (to the end of the
table). `site_day` turns an epoch-millisecond instant into the site's day number with arithmetic
alone, so no browser-zone reader is involved.
"""

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta
from functools import cache

from dbml_sharepoint.analysis.findings import FindingCode
from dbml_sharepoint.analysis.formula.civil import days_of
from dbml_sharepoint.analysis.formula.refusal import FormulaRefusal
from dbml_sharepoint.analysis.timezones import WINDOW_START, zone_table

_FIRST_WINDOW_YEAR = WINDOW_START.year
_LAST_YEAR = 2049
_MS_DAY = 86_400_000
_MS_MINUTE = 60_000
_MEAN_YEAR_MS = 31_556_952_000  # 365.2425 days
_EPOCH_ORDINAL = date(1970, 1, 1).toordinal()
# Self-imposed guard, not a platform fact: a rule that began later leaves too few years behind it.
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


def _literal(value: int) -> str:
    # The syntax reference lists no unary minus, so a negative literal is written as a subtraction.
    return str(value) if value >= 0 else f"(0 - {-value})"


def _first_of_month(year: str, month: int) -> str:
    return days_of(year, str(month), "1")


def _switch_day(year: str, sw: Switch) -> str:
    """Day number of the switch in the calendar `year` (an expression), by the verified rule."""
    # Day 0 is a Thursday and the rule's weekdays count from Sunday, so weekday = (day + 4) % 7.
    if sw.nth > 0:
        first = _first_of_month(year, sw.month)
        return f"({first}) + (({sw.weekday} + 7 - (({first}) + 4) % 7) % 7) + {7 * (sw.nth - 1)}"
    last = f"({_first_of_month(year, sw.month + 1)} - 1)"
    return f"{last} - ((({last} + 4) % 7 - {sw.weekday} + 7) % 7)"


def _span_days(year: int, month: int) -> int:
    return date(year, month, 1).toordinal() - _EPOCH_ORDINAL


def out_of_span_instant(ms: str, rule: ZoneRule) -> str:
    """True when an instant is outside the (UTC) years the rule is verified for."""
    low = _span_days(rule.first_year, 1) * _MS_DAY
    high = _span_days(rule.last_year + 1, 1) * _MS_DAY
    # The quotient is 0 only inside [low, high).
    return f"(floor((({ms}) - {low}) / {high - low}) != 0)"


def site_day(ms: str, rule: ZoneRule) -> str:
    """Day number on the site's calendar of the epoch-millisecond instant `ms`."""
    std = _literal(rule.standard * _MS_MINUTE)
    if rule.daylight is None or rule.switches is None:
        return f"floor((({ms}) + {std}) / {_MS_DAY})"
    to_daylight, to_standard = rule.switches
    dst = _literal(rule.daylight * _MS_MINUTE)
    # The mean-year index can be a year out within a day of new year, where a switch is never
    # within a month, so the state it picks there is still right.
    year = f"(floor((({ms}) + {std}) / {_MEAN_YEAR_MS}) + 1970)"
    up_day, down_day = _switch_day(year, to_daylight), _switch_day(year, to_standard)
    up_at = f"({up_day}) * {_MS_DAY} + {to_daylight.minute * _MS_MINUTE} - {std}"
    down_at = f"({down_day}) * {_MS_DAY} + {to_standard.minute * _MS_MINUTE} - {dst}"
    # Between the two switches in a northern year, outside them in a southern one.
    joiner = " && " if rule.northern else " || "
    flag = f"(({ms}) >= ({up_at}){joiner}({ms}) < ({down_at}))"
    return f"floor((({ms}) + if({flag}, {dst}, {std})) / {_MS_DAY})"
