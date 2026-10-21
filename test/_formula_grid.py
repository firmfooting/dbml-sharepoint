"""The rows a translated formula is checked on, and the check that compares the two evaluators."""

import itertools
import math
from collections.abc import Iterator, Mapping
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from _format_eval import date_field, evaluate_rows
from _formula_reference import DEFAULT_ZONE, ColumnError, evaluate

from dbml_sharepoint.analysis.formula.civil import to_day_number
from dbml_sharepoint.analysis.formula.functions import refs
from dbml_sharepoint.analysis.formula.parse import parse_formula
from dbml_sharepoint.analysis.formula.syntax import ColumnKind

# Text ordering (< >) is unmeasured, so the grid's text values are not evidence for it.
NUMBERS: tuple[float | None, ...] = (None, 0.0, 1.0, 3.0, 12.0, -2.0)
TEXTS: tuple[str | None, ...] = (None, "abc", "ABC", "  a  b ", "0", "false", " ")
# Month ends, year ends, 28 and 29 February (leap and not), the due day and the day after,
# and the days either side of a daylight change in the site zone.
DATES: tuple[date | None, ...] = (
    None,
    date(2025, 12, 31),
    date(2026, 1, 1),
    date(2026, 1, 31),
    date(2026, 2, 28),
    date(2026, 3, 1),
    date(2024, 2, 28),
    date(2024, 2, 29),
    date(2024, 3, 1),
    date(2026, 4, 4),
    date(2026, 4, 5),
    date(2026, 10, 3),
    date(2026, 10, 4),
    date(2026, 10, 20),
    date(2026, 10, 21),
)
UNLISTED = "Unlisted value"
# Created and Modified are never blank.
SYSTEM_MOMENTS = frozenset({"Created", "Modified"})
# Local times either side of midnight and noon, on the days of the dates above.
_TIMES = (time(0, 0, 0), time(0, 0, 1), time(12, 0, 0), time(23, 59, 59))


def instants(zone: str) -> tuple[datetime, ...]:
    """Date-and-time values around the site zone's midnights and its 2026 changes of offset."""
    tz = ZoneInfo(zone)
    found = {
        datetime.combine(day, at, tzinfo=tz).astimezone(UTC)
        for day in DATES
        if day is not None
        for at in _TIMES
    }
    # Each second either side of an hour before and after every change of offset in 2026.
    probe = datetime(2026, 1, 1, tzinfo=UTC)
    step = datetime(2027, 1, 1, tzinfo=UTC)
    previous = probe.astimezone(tz).utcoffset()
    while probe < step:
        probe += timedelta(minutes=30)
        offset = probe.astimezone(tz).utcoffset()
        if offset != previous:
            found.update(probe + timedelta(minutes=m) for m in (-60, -31, -30, -1, 0, 1, 30, 60))
            previous = offset
    # A date written as a UTC midnight and one written 13:30 UTC, which reads the next day.
    for day in DATES:
        if day is not None:
            found.update(datetime.combine(day, at, tzinfo=UTC) for at in (time(0), time(13, 30)))
    return tuple(sorted(found))


def _choice_values(listed: tuple[str, ...]) -> list[str | None]:
    # Every listed value with its case variants, a blank, and a value the column does not list.
    cased = {v for item in listed for v in (item, item.lower(), item.upper())}
    return [None, *sorted(cased), UNLISTED]


def grid(
    columns: Mapping[str, ColumnKind],
    choices: Mapping[str, tuple[str, ...]],
    moments: frozenset[str] = frozenset(),
    zone: str = DEFAULT_ZONE,
) -> Iterator[dict[str, object]]:
    """Every combination of each column's hard values; a blank appears in each column.

    A date column holds an instant as written, so its domain is instants around the site's
    midnights and changes; `moments` marks a column that keeps its time of day.
    """
    domains: list[list[object]] = []
    for name, kind in columns.items():
        match kind:
            case "number":
                domains.append(list(NUMBERS))
            case "text":
                domains.append(list(TEXTS))
            case "date":
                blank = [] if name in SYSTEM_MOMENTS else [None]
                domains.append([*blank, *instants(zone)])
            case "choice":
                domains.append(list(_choice_values(choices.get(name, ()))))
    for combo in itertools.product(*domains):
        yield dict(zip(columns, combo, strict=True))


def _stored(
    formula: str, formulas: Mapping[str, str], kinds: Mapping[str, ColumnKind]
) -> dict[str, ColumnKind]:
    """The stored columns a formula reads, following chained calculated columns."""
    found: dict[str, ColumnKind] = {}
    pending = set(refs(parse_formula(formula)))
    while pending:
        name = pending.pop()
        if name in formulas:
            pending |= refs(parse_formula(formulas[name])) - found.keys()
        else:
            found[name] = kinds[name]
    return found


def _reference(
    formula: str,
    row: Mapping[str, object],
    formulas: Mapping[str, str],
    kinds: Mapping[str, ColumnKind],
    zone: str,
    moments: frozenset[str],
) -> object:
    # A date-only column's value is the site day of its instant; the others keep the instant.
    values = {
        k: v.astimezone(ZoneInfo(zone)).date()
        if isinstance(v, datetime) and k not in moments and k not in SYSTEM_MOMENTS
        else v
        for k, v in row.items()
    }

    def run(text: str) -> object:
        expr = parse_formula(text)
        for name in refs(expr):
            if name in formulas and name not in values:
                values[name] = run(formulas[name])
        return evaluate(expr, values, kinds, zone=zone)

    return run(formula)


def error_rows(
    formula: str,
    formulas: Mapping[str, str],
    kinds: Mapping[str, ColumnKind],
    choices: Mapping[str, tuple[str, ...]],
    *,
    zone: str = DEFAULT_ZONE,
    moments: frozenset[str] = frozenset(),
) -> list[dict[str, object]]:
    """The grid rows on which the formula is a column error; `check_parity` skips them."""
    stored = _stored(formula, formulas, kinds)
    return [
        r
        for r in grid(stored, choices, moments, zone)
        if isinstance(_reference(formula, r, formulas, kinds, zone, moments), ColumnError)
    ]


def _json_row(
    row: Mapping[str, object], kinds: Mapping[str, ColumnKind]
) -> dict[str, object]:
    # A blank text or choice field reads as '' in a formatter (Learn's `[$Field] == ''` blank test).
    # A date column's value is its epoch milliseconds, the instant as stored.
    sent: dict[str, object] = {}
    for k, v in row.items():
        if isinstance(v, datetime):
            sent[k] = date_field(int(v.timestamp() * 1000))
        elif v is None and kinds[k] == "date":
            sent[k] = date_field(None)
        else:
            sent[k] = "" if v is None and kinds[k] in ("text", "choice") else v
    return sent


def _same(expected: object, got: object) -> bool:
    if expected is None:
        return got in (None, "")
    if isinstance(expected, bool):
        return got is expected
    if isinstance(expected, float):
        return (
            isinstance(got, int | float)
            and not isinstance(got, bool)
            and math.isclose(got, expected, rel_tol=1e-9, abs_tol=1e-9)
        )
    return got == expected


def check_parity(
    formula: str,
    expression: str,
    formulas: Mapping[str, str],
    kinds: Mapping[str, ColumnKind],
    choices: Mapping[str, tuple[str, ...]],
    browsers: tuple[str, ...],
    nows: tuple[str, ...] = (),
    *,
    zone: str = DEFAULT_ZONE,
    moments: frozenset[str] = frozenset(),
) -> None:
    """Fail when the expression differs from the formula on any grid row, in any browser zone.

    Rows on which the formula is a column error are skipped (see `error_rows`).
    """
    rows = list(grid(_stored(formula, formulas, kinds), choices, moments, zone))
    # A date result is shown as its day number.
    expected = [
        to_day_number(e) if isinstance(e, date) else e
        for e in (_reference(formula, r, formulas, kinds, zone, moments) for r in rows)
    ]
    kept = [(r, e) for r, e in zip(rows, expected, strict=True) if not isinstance(e, ColumnError)]
    assert kept, "every grid row is a column error, so nothing was compared"
    stored = _stored(formula, formulas, kinds)
    sent = [_json_row(r, stored) for r, _ in kept]
    failures: list[str] = []
    for browser, now in itertools.product(browsers, nows or ("2026-10-20T12:00:00Z",)):
        got = evaluate_rows(expression, sent, browser_tz=browser, now=now)
        failures += [
            f"{formula!r} vs {expression!r} in {browser} at {now}: "
            f"row {row} gave {g!r}, expected {e!r}"
            for (row, e), g in zip(kept, got, strict=True)
            if not _same(e, g)
        ]
    assert not failures, f"{len(failures)} differing rows, first: {failures[0]}"
