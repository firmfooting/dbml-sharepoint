# test/test_threshold_rows.py
"""The fixture's composition is the experiment's control.

Every number here is one the threshold probe's expectations are written
against. A row generator that silently changes a count turns "this query
returned fewer rows than expected" from a finding into a mystery.
"""

import csv
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

MANUAL = Path(__file__).parent / "manual"


def _load() -> ModuleType:
    """Import by path: `test` is a CPython stdlib package name, so importing
    through it is a collision waiting to happen on someone else's machine.
    Same reason test_probes.py loads render_probes this way."""
    spec = importlib.util.spec_from_file_location(
        "dbmlsp_make_threshold_rows", MANUAL / "make_threshold_rows.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_closed_at_is_blank_on_exactly_a_fifth_of_rows() -> None:
    m = _load()
    rows = m.build_rows()
    blank = [r for r in rows if r["ClosedAt"] == ""]
    assert len(rows) == 6000
    assert len(blank) == 1200


def test_rare_bucket_is_selective_and_exactly_counted() -> None:
    m = _load()
    rows = m.build_rows()
    rare = [r for r in rows if r["Bucket"] == m.RARE_BUCKET]
    assert len(rare) == 60


def test_shadow_is_byte_identical_to_bucket() -> None:
    """The load-bearing control. The two columns must differ ONLY in whether
    an index exists, so a divergence cannot be blamed on data shape."""
    m = _load()
    assert all(r["Shadow"] == r["Bucket"] for r in m.build_rows())


def test_sort_bait_is_high_cardinality_and_deterministic() -> None:
    m = _load()
    first = m.build_rows()
    assert len({r["SortBait"] for r in first}) == 6000
    assert [r["SortBait"] for r in m.build_rows()] == [r["SortBait"] for r in first]


def test_owner_and_parent_are_blank_until_ids_are_supplied() -> None:
    """The generator runs before the probe has told anyone the ids, so a run
    without them must still produce loadable files rather than the string
    'None' in a Person column."""
    m = _load()
    rows = m.build_rows()
    assert all(r["OwnerId"] == "" for r in rows)
    assert all(r["ParentId"] == "" for r in rows)


def test_owner_is_set_on_a_quarter_of_rows_when_supplied() -> None:
    m = _load()
    rows = m.build_rows(owner_id="7", parent_id="1")
    assert len([r for r in rows if r["OwnerId"] == "7"]) == 1500
    assert all(r["ParentId"] == "1" for r in rows)


def test_split_totals_land_exactly_on_the_checkpoints() -> None:
    """Each file advances the list to the next checkpoint. If the cumulative
    totals drift, every snapshot is filed under a row count the list never
    actually held."""
    m = _load()
    plan = m.split_plan()
    assert [last for _, _, last in plan] == list(m.CHECKPOINTS)
    assert [last - first + 1 for _, first, last in plan] == [1000, 2000, 1900, 200, 900]
    assert sum(last - first + 1 for _, first, last in plan) == m.TOTAL


def test_split_rows_are_contiguous_with_no_gaps_or_repeats() -> None:
    m = _load()
    covered: list[int] = []
    for _, first, last in m.split_plan():
        covered.extend(range(first, last + 1))
    assert covered == list(range(1, m.TOTAL + 1))


def test_file_names_encode_the_resulting_list_total() -> None:
    m = _load()
    names = [m.file_name(seq, last) for seq, _, last in m.split_plan()]
    assert names == [
        "threshold-rows-01-to-1000.csv",
        "threshold-rows-02-to-3000.csv",
        "threshold-rows-03-to-4900.csv",
        "threshold-rows-04-to-5100.csv",
        "threshold-rows-05-to-6000.csv",
    ]


def test_written_csvs_carry_internal_names_and_the_right_row_counts(tmp_path: Path) -> None:
    m = _load()
    written = m.write_csvs(m.build_rows(owner_id="7", parent_id="1"), tmp_path)
    assert [p.name for p in written] == [
        m.file_name(seq, last) for seq, _, last in m.split_plan()
    ]
    with written[0].open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == list(m.HEADERS)
        first_file = list(reader)
    assert len(first_file) == 1000
    assert first_file[0]["Title"] == "Row 000001"
    # The Person and Lookup headers carry the `Id` suffix REST requires.
    assert "OwnerId" in m.HEADERS
    assert "Owner" not in m.HEADERS
    assert "ParentId" in m.HEADERS
    assert "Parent" not in m.HEADERS


def test_the_last_file_ends_on_the_last_row(tmp_path: Path) -> None:
    m = _load()
    written = m.write_csvs(m.build_rows(), tmp_path)
    with written[-1].open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 900
    assert rows[-1]["Title"] == f"Row {m.TOTAL:06d}"
