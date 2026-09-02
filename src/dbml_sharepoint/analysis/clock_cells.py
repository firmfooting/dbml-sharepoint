# src/dbml_sharepoint/analysis/clock_cells.py
"""Every clock cell the renderer can meet, with its evidence or its refusal.

A clock cell is one sentinel (`today`, `today+N or today-N`, `now`) on one kind of date
column (`date`, `datetime`, `calculated_date`) for one condition target (a
validation formula, a CAML view filter, a client-side expression). Each cell
is declared here as one of:

- ``measured``: emitted, and a named live run observed the rendering behave;
- ``unmeasured``: emitted, and nothing has observed it (the ratchet in
  `test/test_clock_cells.py` lists these with a reason each);
- ``clock``: emitted, and it reads the formula clock that was measured 16 to
  20 hours behind the site on 2026-09-02, which the validator warns about;
- ``refused``: the renderer raises, and the validator reports the finding.

The renderer does not read this table. The test renders a canonical leaf per
cell through the public renderers and holds them to what is declared here,
so a rendering cannot change without its evidence changing with it. The
scope is the three condition targets; the `[today]` column default is not a
condition and its evidence is `DEFAULT_EVIDENCE`, for the verification
artifact.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

from dbml_sharepoint.analysis.condition_rendering import (
    CAML,
    EXPRESSION,
    VALIDATION,
    ConditionRefusalKind,
)
from dbml_sharepoint.analysis.typemap import DATE_TYPES, NOW_SENTINEL, TODAY_SENTINEL

Sentinel = Literal["today", "today_offset", "now"]
Status = Literal["measured", "unmeasured", "clock", "refused"]

SENTINELS: tuple[Sentinel, ...] = ("today", "today_offset", "now")
COLUMN_KINDS: tuple[str, ...] = tuple(sorted(DATE_TYPES))
TARGETS: tuple[str, ...] = (VALIDATION, CAML, EXPRESSION)


@dataclass(frozen=True)
class Evidence:
    """One live run: the repo file that records it, when, and on which site."""

    probe: str
    measured: str
    zone: str
    note: str


@dataclass(frozen=True)
class ClockCell:
    sentinel: Sentinel
    column_kind: str
    target: str
    status: Status
    #: Validation: (op, spelling) -> the whole formula for `Leaf("D", op, spelling)`.
    #: CAML: spelling -> the `<Value>` element the clock renders to.
    renderings: Mapping[Any, str] = field(default_factory=dict)
    evidence: Evidence | None = None
    refusal: ConditionRefusalKind | None = None

    def __post_init__(self) -> None:
        if self.status == "measured" and self.evidence is None:
            raise ValueError(f"{self.id}: a measured cell needs evidence")
        if self.status == "refused" and self.refusal is None:
            raise ValueError(f"{self.id}: a refused cell needs its refusal")
        if (self.status == "refused") != (not self.renderings):
            raise ValueError(f"{self.id}: renderings belong to every cell but a refused one")

    @property
    def id(self) -> str:
        return f"{self.target}/{self.column_kind}/{self.sentinel}"


def sentinel_of(value: object, column_type: str) -> Sentinel | None:
    """Which clock sentinel a leaf value is, on a date-ish column; else None."""
    if column_type not in DATE_TYPES or not isinstance(value, str):
        return None
    if NOW_SENTINEL.match(value):
        return "now"
    match = TODAY_SENTINEL.match(value)
    if match is None:
        return None
    return "today_offset" if match.group(2) and int(match.group(2)) else "today"


def cell_for(sentinel: str, column_kind: str, target: str) -> ClockCell:
    return _BY_ID[f"{target}/{column_kind}/{sentinel}"]


_SAVE_RULES = "src/dbml_sharepoint/analysis/save_rules.py"
_DATETIME_PROBE = "test/manual/datetime-sentinel-probe.js"
_AUS = "AUS Eastern (UTC+10)"

#: `[today]` as a column default, which is not a condition target.
DEFAULT_EVIDENCE = Evidence(
    probe=_SAVE_RULES,
    measured="2026-09-02",
    zone=_AUS,
    note=(
        "the modern form prefilled the site's date; a REST create with the "
        "column omitted stored the current instant; under a [Modified] rule "
        "five REST creates and a form-endpoint create all saved, the default "
        "and Modified stamped to the same second"
    ),
)


def _save_instant(*, sign: str, ops: dict[str, str]) -> dict[Any, str]:
    """The date-only renderings against [Modified] for one offset spelling."""
    return {(op, sign): rendering for op, rendering in ops.items()}


def _against_modified(value: str, shift_day: str, shift_next: str) -> dict[Any, str]:
    day, nxt = f"[D]{shift_day}", f"[D]{shift_next}"
    return _save_instant(sign=value, ops={
        "leq": f"{day}<=[Modified]",
        "lt": f"{nxt}<=[Modified]",
        "gt": f"{day}>[Modified]",
        "geq": f"{nxt}>[Modified]",
        "eq": f"AND({day}<=[Modified],{nxt}>[Modified])",
        "neq": f"OR({day}>[Modified],{nxt}<=[Modified])",
    })


def _plain(value: str, literal: str) -> dict[Any, str]:
    symbols = {"leq": "<=", "lt": "<", "gt": ">", "geq": ">=", "eq": "=", "neq": "<>"}
    return {(op, value): f"[D]{symbol}{literal}" for op, symbol in symbols.items()}


_TODAY_XML = '<Value Type="DateTime"><Today/></Value>'
_OFFSET_XML = {
    "today+3": '<Value Type="DateTime"><Today OffsetDays="3"/></Value>',
    "today-1": '<Value Type="DateTime"><Today OffsetDays="-1"/></Value>',
}
_NOW_XML = '<Value Type="DateTime" IncludeTimeValue="TRUE"><Today/></Value>'


def _refused(
    sentinel: Sentinel, kind: str, target: str, refusal: ConditionRefusalKind,
) -> ClockCell:
    return ClockCell(sentinel, kind, target, "refused", refusal=refusal)


CELLS: tuple[ClockCell, ...] = (
    # ---- validation ------------------------------------------------------
    ClockCell(
        "today", "date", VALIDATION, "measured",
        _against_modified("today", "", "+1"),
        evidence=Evidence(
            _SAVE_RULES, "2026-09-02", _AUS,
            "today saved, tomorrow and thirty days out refused, an update to "
            "today saved; through REST and the modern form",
        ),
    ),
    ClockCell(
        "today_offset", "date", VALIDATION, "unmeasured",
        {**_against_modified("today+3", "-3", "-2"), **_against_modified("today-1", "+1", "+2")},
    ),
    _refused("now", "date", VALIDATION, ConditionRefusalKind.NOW_ON_A_DATE_COLUMN),
    _refused("today", "datetime", VALIDATION, ConditionRefusalKind.TODAY_ON_A_DATETIME_COLUMN),
    ClockCell(
        "today_offset", "datetime", VALIDATION, "clock",
        {**_plain("today+3", "TODAY()+3"), **_plain("today-1", "TODAY()-1")},
    ),
    ClockCell(
        "now", "datetime", VALIDATION, "measured",
        _plain("now", "[Modified]"),
        evidence=Evidence(
            _SAVE_RULES, "2026-09-02", _AUS,
            "an hour ago saved, an hour ahead refused; an update stamped five "
            "seconds before its own save saved, one an hour ahead refused",
        ),
    ),
    _refused("today", "calculated_date", VALIDATION, ConditionRefusalKind.OPERAND_TYPE_UNSUPPORTED),
    _refused(
        "today_offset", "calculated_date", VALIDATION,
        ConditionRefusalKind.OPERAND_TYPE_UNSUPPORTED,
    ),
    _refused("now", "calculated_date", VALIDATION, ConditionRefusalKind.OPERAND_TYPE_UNSUPPORTED),
    # ---- caml ------------------------------------------------------------
    ClockCell(
        "today", "date", CAML, "measured", {"today": _TODAY_XML},
        evidence=Evidence(
            _SAVE_RULES, "2026-09-02", _AUS,
            "`Eq <Today/>` on a date-only column returned the rows dated the "
            "site's day and not the rows a lagging =TODAY() default had filled",
        ),
    ),
    ClockCell(
        "today_offset", "date", CAML, "measured", dict(_OFFSET_XML),
        evidence=Evidence(
            _SAVE_RULES, "2026-09-02", _AUS,
            "`Eq <Today OffsetDays='-1'/>` on a date-only column returned the "
            "rows dated the site's previous day",
        ),
    ),
    _refused("now", "date", CAML, ConditionRefusalKind.NOW_ON_A_DATE_COLUMN),
    ClockCell(
        "today", "datetime", CAML, "measured", {"today": _TODAY_XML},
        evidence=Evidence(
            _DATETIME_PROBE, "2026-07-29", _AUS,
            "C5: plain <Today/> on a datetime column is date-granular, "
            "returning yesterday's row only",
        ),
    ),
    ClockCell("today_offset", "datetime", CAML, "unmeasured", dict(_OFFSET_XML)),
    ClockCell(
        "now", "datetime", CAML, "measured", {"now": _NOW_XML},
        evidence=Evidence(
            _DATETIME_PROBE, "2026-07-29", _AUS,
            "C4, C6, C7: <Today/> with IncludeTimeValue compares against the "
            "instant, survives the saved ViewQuery, and the saved view "
            "returns the instant-discriminated rows",
        ),
    ),
    ClockCell("today", "calculated_date", CAML, "unmeasured", {"today": _TODAY_XML}),
    ClockCell("today_offset", "calculated_date", CAML, "unmeasured", dict(_OFFSET_XML)),
    _refused("now", "calculated_date", CAML, ConditionRefusalKind.NOW_ON_A_DATE_COLUMN),
    # ---- expression ------------------------------------------------------
    _refused("today", "date", EXPRESSION, ConditionRefusalKind.TODAY_UNSUPPORTED_BY_TARGET),
    _refused("today_offset", "date", EXPRESSION, ConditionRefusalKind.TODAY_UNSUPPORTED_BY_TARGET),
    _refused("now", "date", EXPRESSION, ConditionRefusalKind.NOW_ON_A_DATE_COLUMN),
    _refused("today", "datetime", EXPRESSION, ConditionRefusalKind.TODAY_UNSUPPORTED_BY_TARGET),
    _refused(
        "today_offset", "datetime", EXPRESSION,
        ConditionRefusalKind.TODAY_UNSUPPORTED_BY_TARGET,
    ),
    _refused("now", "datetime", EXPRESSION, ConditionRefusalKind.NOW_UNSUPPORTED_BY_TARGET),
    _refused("today", "calculated_date", EXPRESSION, ConditionRefusalKind.OPERAND_TYPE_UNSUPPORTED),
    _refused(
        "today_offset", "calculated_date", EXPRESSION,
        ConditionRefusalKind.OPERAND_TYPE_UNSUPPORTED,
    ),
    _refused("now", "calculated_date", EXPRESSION, ConditionRefusalKind.OPERAND_TYPE_UNSUPPORTED),
)

_BY_ID = {cell.id: cell for cell in CELLS}
