"""The rows a translated formula is checked on, and the check that compares the two evaluators."""

import itertools
import math
from collections.abc import Iterator, Mapping
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from _format_eval import evaluate_rows
from _formula_reference import DEFAULT_ZONE, ColumnError, evaluate, instant

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


def _choice_values(listed: tuple[str, ...]) -> list[str | None]:
    # Every listed value with its case variants, a blank, and a value the column does not list.
    cased = {v for item in listed for v in (item, item.lower(), item.upper())}
    return [None, *sorted(cased), UNLISTED]


def grid(
    columns: Mapping[str, ColumnKind], choices: Mapping[str, tuple[str, ...]]
) -> Iterator[dict[str, object]]:
    """Every combination of each column's hard values; a blank appears in each column."""
    domains: list[list[object]] = []
    for name, kind in columns.items():
        match kind:
            case "number":
                domains.append(list(NUMBERS))
            case "text":
                domains.append(list(TEXTS))
            case "date":
                domains.append(list(DATES))
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
) -> object:
    values = dict(row)

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
) -> list[dict[str, object]]:
    """The grid rows on which the formula is a column error; `check_parity` skips them."""
    stored = _stored(formula, formulas, kinds)
    return [
        r
        for r in grid(stored, choices)
        if isinstance(_reference(formula, r, formulas, kinds, zone), ColumnError)
    ]


def _json_row(
    row: Mapping[str, object], kinds: Mapping[str, ColumnKind], zone: str
) -> dict[str, object]:
    # A blank text or choice field reads as '' in a formatter (Learn's `[$Field] == ''` blank test).
    return {
        k: instant(v, zone)
        if isinstance(v, date)
        else ("" if v is None and kinds[k] in ("text", "choice") else v)
        for k, v in row.items()
    }


def _same(expected: object, got: object, zone: str) -> bool:
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
    if isinstance(expected, date):
        if not isinstance(got, str):
            return False
        moment = datetime.fromisoformat(got).astimezone(UTC)
        return moment.astimezone(ZoneInfo(zone)).date() == expected
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
) -> None:
    """Fail when the expression differs from the formula on any grid row, in any browser zone.

    Rows on which the formula is a column error are skipped (see `error_rows`).
    """
    rows = list(grid(_stored(formula, formulas, kinds), choices))
    expected = [_reference(formula, r, formulas, kinds, zone) for r in rows]
    kept = [(r, e) for r, e in zip(rows, expected, strict=True) if not isinstance(e, ColumnError)]
    assert kept, "every grid row is a column error, so nothing was compared"
    stored = _stored(formula, formulas, kinds)
    sent = [_json_row(r, stored, zone) for r, _ in kept]
    failures: list[str] = []
    for browser, now in itertools.product(browsers, nows or ("2026-10-20T12:00:00Z",)):
        got = evaluate_rows(expression, sent, browser_tz=browser, now=now)
        failures += [
            f"{formula!r} vs {expression!r} in {browser} at {now}: "
            f"row {row} gave {g!r}, expected {e!r}"
            for (row, e), g in zip(kept, got, strict=True)
            if not _same(e, g, zone)
        ]
    assert not failures, f"{len(failures)} differing rows, first: {failures[0]}"
