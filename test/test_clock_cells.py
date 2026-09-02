# test/test_clock_cells.py
"""The clock cell table holds the renderer to its evidence.

`analysis/clock_cells.py` declares every (sentinel, column kind, target)
cell as a rendering with the run that observed it, as a rendering nobody
has observed, as one that reads the lagging formula clock, or as refused.
The renderer does not read the table; these tests render a canonical leaf
per cell through the public renderers and compare, so a rendering cannot
change without its evidence changing with it, and no cell can be emitted
that the table does not know about.
"""
from itertools import product
from pathlib import Path
from typing import Any

import pytest

import dbml_sharepoint
from dbml_sharepoint.analysis import clock_cells
from dbml_sharepoint.analysis.clock_cells import (
    CELLS,
    COLUMN_KINDS,
    SENTINELS,
    TARGETS,
    ClockCell,
    Evidence,
    cell_for,
    sentinel_of,
)
from dbml_sharepoint.analysis.condition_rendering import (
    CAML,
    EXPRESSION,
    VALIDATION,
    ConditionRefusal,
    ConditionRefusalKind,
    to_caml,
    to_expression,
    to_validation,
)
from dbml_sharepoint.analysis.typemap import DATE_TYPES
from dbml_sharepoint.model.conditions import Group, Leaf

REPO = Path(dbml_sharepoint.__file__).resolve().parents[2]
RENDER = {VALIDATION: to_validation, CAML: to_caml, EXPRESSION: to_expression}
COMPARISONS = ("leq", "lt", "gt", "geq", "eq", "neq")
#: The spellings the test renders for each sentinel. Two offsets, one each
#: side of zero, because `_shift` has a branch per sign.
SPELLINGS = {"today": ("today",), "today_offset": ("today+3", "today-1"), "now": ("now",)}

#: Cells the renderer emits without a live observation behind them. A
#: ratchet: an entry needs a reason, nothing measured may appear here, and
#: an entry leaves when a probe or the verification artifact observes it.
EMITTED_WITHOUT_EVIDENCE = {
    "validation/date/today_offset": (
        "the shifted form `[D]-N<=[Modified]` has never been saved live; only "
        "the offset-free form was (2026-09-02)"
    ),
    "caml/datetime/today_offset": (
        "`<Today OffsetDays>` was observed on a date-only column (2026-09-02) "
        "and plain `<Today/>` on a datetime (2026-07-29), never the offset on a "
        "datetime"
    ),
    "caml/calculated_date/today": (
        "shipped views filter a calculated date with `<Today/>` (risk-register "
        "NextReviewDue) and no probe row has observed the result"
    ),
    "caml/calculated_date/today_offset": (
        "as for the bare form: relied on by shipped views, observed by no probe"
    ),
}

#: An independent record of what each measured run saw, keyed by cell id
#: and holding only the operator the run exercised. Kept apart from the
#: table on purpose: editing a cell to match a renderer change cannot also
#: edit this, so a measured cell drifting from its measurement fails here.
MEASURED: dict[str, dict[Any, str]] = {
    "validation/date/today": {("leq", "today"): "[D]<=[Modified]"},
    "validation/datetime/now": {("leq", "now"): "[D]<=[Modified]"},
    "caml/date/today": {"today": '<Value Type="DateTime"><Today/></Value>'},
    "caml/date/today_offset": {
        "today-1": '<Value Type="DateTime"><Today OffsetDays="-1"/></Value>',
    },
    "caml/datetime/today": {"today": '<Value Type="DateTime"><Today/></Value>'},
    "caml/datetime/now": {"now": '<Value Type="DateTime" IncludeTimeValue="TRUE"><Today/></Value>'},
}


def _condition(op: str, value: str) -> Group:
    item = [value] if op in ("in", "not_in") else value
    return Group("all_of", (Leaf(field="D", op=op, value=item),))


def test_every_cell_exists_exactly_once() -> None:
    ids = [cell.id for cell in CELLS]
    assert len(ids) == len(set(ids))
    expected = {
        f"{target}/{kind}/{sentinel}"
        for sentinel, kind, target in product(SENTINELS, COLUMN_KINDS, TARGETS)
    }
    assert set(ids) == expected
    assert set(COLUMN_KINDS) == DATE_TYPES
    assert set(TARGETS) == {VALIDATION, CAML, EXPRESSION}


def test_a_cell_cannot_claim_a_status_its_fields_do_not_support() -> None:
    evidence = Evidence(probe="x", measured="2026-01-01", zone="UTC", note="n")
    with pytest.raises(ValueError, match="evidence"):
        ClockCell("today", "date", VALIDATION, "measured", {("leq", "today"): "x"})
    with pytest.raises(ValueError, match="refusal"):
        ClockCell("today", "date", VALIDATION, "refused", {})
    with pytest.raises(ValueError, match="renderings"):
        ClockCell(
            "today", "date", VALIDATION, "refused", {("leq", "today"): "x"},
            refusal=ConditionRefusalKind.TODAY_UNSUPPORTED_BY_TARGET,
        )
    with pytest.raises(ValueError, match="renderings"):
        ClockCell("today", "date", VALIDATION, "measured", {}, evidence=evidence)


@pytest.mark.parametrize("cell", CELLS, ids=lambda c: c.id)
def test_the_renderer_does_what_the_table_declares(cell: ClockCell) -> None:
    render = RENDER[cell.target]
    types = {"D": cell.column_kind}
    ops = COMPARISONS + (("in", "not_in") if cell.target == CAML else ())
    if cell.status == "refused":
        for op in ops:
            for value in SPELLINGS[cell.sentinel]:
                with pytest.raises(ConditionRefusal) as caught:
                    render(_condition(op, value), types)
                assert caught.value.kind is cell.refusal, (op, value)
        return
    if cell.target == CAML:
        # The clock lives in the <Value> element; the operator wrapping
        # around it is CAML rendering, pinned elsewhere.
        for value in SPELLINGS[cell.sentinel]:
            element = cell.renderings[value]
            for op in ops:
                rendered = render(_condition(op, value), types)
                assert rendered.count(element) == 1, (op, value, rendered)
        return
    for op in COMPARISONS:
        for value in SPELLINGS[cell.sentinel]:
            assert render(_condition(op, value), types) == cell.renderings[(op, value)], (op, value)


def test_renderings_are_declared_for_every_spelling_the_test_renders() -> None:
    for cell in CELLS:
        if cell.status == "refused":
            continue
        if cell.target == CAML:
            assert set(cell.renderings) == set(SPELLINGS[cell.sentinel]), cell.id
        else:
            expected = {(op, value) for op in COMPARISONS for value in SPELLINGS[cell.sentinel]}
            assert set(cell.renderings) == expected, cell.id


def test_unmeasured_cells_are_on_the_ratchet_and_nothing_measured_is() -> None:
    unmeasured = {cell.id for cell in CELLS if cell.status == "unmeasured"}
    assert unmeasured == set(EMITTED_WITHOUT_EVIDENCE)
    for cell_id, reason in EMITTED_WITHOUT_EVIDENCE.items():
        assert reason.strip(), cell_id
        assert cell_for(*reversed(cell_id.split("/"))).status == "unmeasured"


def test_measured_cells_agree_with_the_independent_record() -> None:
    measured = {cell.id for cell in CELLS if cell.status == "measured"}
    assert measured == set(MEASURED)
    for cell_id, seen in MEASURED.items():
        cell = cell_for(*reversed(cell_id.split("/")))
        for key, rendering in seen.items():
            assert cell.renderings[key] == rendering, (cell_id, key)


def test_every_measurement_names_a_file_that_exists() -> None:
    for cell in CELLS:
        if cell.evidence is not None:
            assert (REPO / cell.evidence.probe).is_file(), (cell.id, cell.evidence.probe)
            assert cell.evidence.measured[:4].isdigit(), cell.id
    assert (REPO / clock_cells.DEFAULT_EVIDENCE.probe).is_file()


def test_the_lagging_clock_cell_is_the_only_one_left() -> None:
    """The point of the table: after 2026-09-02, exactly one emitted shape
    still reads TODAY(), and the validator warns about it."""
    assert [cell.id for cell in CELLS if cell.status == "clock"] == [
        "validation/datetime/today_offset",
    ]


@pytest.mark.parametrize(
    ("value", "column_type", "expected"),
    [
        ("today", "date", "today"),
        ("today+0", "date", "today"),
        ("today-7", "datetime", "today_offset"),
        ("today+30", "calculated_date", "today_offset"),
        ("now", "datetime", "now"),
        ("now", "date", "now"),
        ("today", "nvarchar", None),
        ("2026-09-02", "date", None),
        (3, "int", None),
    ],
)
def test_sentinel_of_classifies_a_leaf_value(
    value: object, column_type: str, expected: str | None,
) -> None:
    assert sentinel_of(value, column_type) == expected
