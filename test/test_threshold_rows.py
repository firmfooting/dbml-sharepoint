# test/test_threshold_rows.py
"""The fixture's composition is the experiment's control.

Every number here is one the threshold probe's expectations are written
against. A row generator that silently changes a count turns "this query
returned fewer rows than expected" from a finding into a mystery.

Note what several of these assert: properties of the BYTES ON DISK across all
five files, not of `build_rows()`. A review of an earlier version broke
`write_csvs` so that 1900 rows were duplicated and 1900 omitted — same file
names, same per-file counts, same 6000 total — and every assertion in this file
passed, because nothing read the union.
"""

import csv
import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

MANUAL = Path(__file__).parent / "manual"
GENERATOR = MANUAL / "make_threshold_rows.py"


def _load() -> ModuleType:
    """Import by path: `test` is a CPython stdlib package name, so importing
    through it is a collision waiting to happen on someone else's machine.
    Same reason test_probes.py loads render_probes this way."""
    spec = importlib.util.spec_from_file_location(
        "dbmlsp_make_threshold_rows", GENERATOR,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _union(out_dir: Path) -> list[dict[str, str]]:
    """Every row of every written file, in load order."""
    m = _load()
    rows: list[dict[str, str]] = []
    for sequence, _, last in m.split_plan():
        target = out_dir / m.file_name(sequence, last)
        with target.open(encoding="utf-8", newline="") as handle:
            rows.extend(csv.DictReader(handle))
    return rows


# === Composition ============================================================


def test_every_filtered_population_is_the_same_size() -> None:
    """Matched selectivity is the design. Each of these filters differs from
    `Bucket eq 'Z'` in exactly ONE respect — the index, the operator, or the
    field type — which is only true while the row counts agree."""
    m = _load()
    rows = m.build_rows(owner_id="7", parent_id="1")
    assert len(rows) == 6000
    assert m.MATCHING_ROWS == 60
    assert len([r for r in rows if r["Bucket"] == m.RARE_BUCKET]) == 60
    assert len([r for r in rows if r["Shadow"] == m.RARE_BUCKET]) == 60
    assert len([r for r in rows if r["ClosedAt"] == ""]) == 60
    assert len([r for r in rows if r["OwnerId"] == "7"]) == 60
    assert len([r for r in rows if r["ParentId"] == "1"]) == 60


def test_the_filtered_populations_are_pairwise_disjoint() -> None:
    """No row may be both a `Z` and a blank `ClosedAt`. Overlap would let one
    result be read as a consequence of another — and in the first draft every
    single `Z` row was also blank and also owned, because all three offsets
    were multiples of 100."""
    m = _load()
    rows = m.build_rows(owner_id="7", parent_id="1")
    populations = {
        "bucket": {i for i, r in enumerate(rows) if r["Bucket"] == m.RARE_BUCKET},
        "null": {i for i, r in enumerate(rows) if r["ClosedAt"] == ""},
        "owner": {i for i, r in enumerate(rows) if r["OwnerId"] == "7"},
        "parent": {i for i, r in enumerate(rows) if r["ParentId"] == "1"},
    }
    for left, left_rows in populations.items():
        for right, right_rows in populations.items():
            if left < right:
                assert not (left_rows & right_rows), f"{left} overlaps {right}"


def test_shadow_is_byte_identical_to_bucket() -> None:
    """The load-bearing control. The two columns must differ ONLY in whether
    an index exists, so a divergence cannot be blamed on data shape."""
    m = _load()
    assert all(r["Shadow"] == r["Bucket"] for r in m.build_rows())


def test_closed_at_is_iso_8601_utc_with_a_z() -> None:
    """SharePoint REST rejects the `+00:00` that isoformat() emits. Unpinned,
    dropping the replace() would only surface as silent per-item batch
    failures, batch creation being non-transactional."""
    m = _load()
    assert m.closed_at_for(1) == "2020-01-02T00:00:00Z"
    assert all("+" not in r["ClosedAt"] for r in m.build_rows())


def test_sort_bait_is_pinned_to_literals_that_survive_a_new_process() -> None:
    """`len(set(...)) == 6000` cannot fail while the `-{row}` suffix exists, so
    it proves nothing about the hash. And an in-process determinism check
    passes for `hash()`, which is salted per interpreter — regenerating
    mid-run would then leave the list holding a mixture and void the sort
    observation. Literals are what actually survives a process boundary.
    """
    m = _load()
    assert m.sort_bait_for(1) == "435761-000001"
    assert m.sort_bait_for(6000) == "566000-006000"
    baits = [r["SortBait"] for r in m.build_rows()]
    # The hash half alone must be injective, suffix removed.
    assert len({bait.split("-")[0] for bait in baits}) == 6000
    # And it must not be in row order, or it is not bait.
    assert sorted(baits) != baits


def test_sort_bait_is_identical_in_a_separate_interpreter() -> None:
    """The claim is "byte-identical on every run", so cross the process
    boundary the in-process check cannot."""
    m = _load()
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c",
         f"import importlib.util as u; "
         f"s = u.spec_from_file_location('g', r'{GENERATOR}'); "
         f"g = u.module_from_spec(s); s.loader.exec_module(g); "
         f"print(g.sort_bait_for(1), g.sort_bait_for(6000))"],
        capture_output=True, text=True, check=True,
    )
    assert result.stdout.split() == [m.sort_bait_for(1), m.sort_bait_for(6000)]


def test_owner_and_parent_are_blank_until_ids_are_supplied() -> None:
    """The generator runs before the probe has told anyone the ids, so a run
    without them must still produce loadable files rather than the string
    'None' in a Person column."""
    m = _load()
    rows = m.build_rows()
    assert all(r["OwnerId"] == "" for r in rows)
    assert all(r["ParentId"] == "" for r in rows)


# === The split ==============================================================


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


# === The bytes on disk ======================================================


def test_the_written_files_hold_every_row_exactly_once(tmp_path: Path) -> None:
    """The assertion an earlier draft was missing. Per-file counts and the
    grand total can all be right while rows are duplicated and omitted in
    equal measure — only the union catches it, and the probe's RUNCNT guard
    would read the resulting list as ON CHECKPOINT and trust the whole run."""
    m = _load()
    m.write_csvs(m.build_rows(owner_id="7", parent_id="1"), tmp_path)
    titles = [r["Title"] for r in _union(tmp_path)]
    assert titles == [f"Row {i:06d}" for i in range(1, m.TOTAL + 1)]


def test_the_written_files_preserve_every_composition_invariant(tmp_path: Path) -> None:
    """Measured across the union, of the actual deliverable. Everything else in
    this file tests build_rows(); the operator loads these bytes."""
    m = _load()
    m.write_csvs(m.build_rows(owner_id="7", parent_id="1"), tmp_path)
    rows = _union(tmp_path)
    assert len(rows) == m.TOTAL
    assert len([r for r in rows if r["Bucket"] == m.RARE_BUCKET]) == 60
    assert len([r for r in rows if r["ClosedAt"] == ""]) == 60
    assert len([r for r in rows if r["OwnerId"] == "7"]) == 60
    assert len([r for r in rows if r["ParentId"] == "1"]) == 60
    assert all(r["Shadow"] == r["Bucket"] for r in rows)


def test_written_csvs_carry_the_internal_column_names(tmp_path: Path) -> None:
    m = _load()
    written = m.write_csvs(m.build_rows(), tmp_path)
    with written[0].open(encoding="utf-8", newline="") as handle:
        assert csv.DictReader(handle).fieldnames == list(m.HEADERS)
    # The Person and Lookup headers carry the `Id` suffix REST requires.
    assert "OwnerId" in m.HEADERS
    assert "Owner" not in m.HEADERS
    assert "ParentId" in m.HEADERS
    assert "Parent" not in m.HEADERS


def test_a_row_count_that_does_not_match_the_run_plan_is_refused(tmp_path: Path) -> None:
    """Short input silently produced header-only tail files, and long input
    silently dropped the overflow. Either hands over a directory that looks
    like a complete run plan."""
    m = _load()
    with pytest.raises(ValueError, match="run plan needs exactly 6000"):
        m.write_csvs(m.build_rows(total=1000), tmp_path)


def test_writing_clears_a_previous_run_plans_files(tmp_path: Path) -> None:
    """A shortened plan would otherwise leave the old tail sitting beside the
    new files, loadable and indistinguishable — and the file names are what
    the operator reads the run plan off."""
    m = _load()
    stale = tmp_path / m.file_name(9, 99999)
    stale.write_text("Title\nstale\n", encoding="utf-8")
    m.write_csvs(m.build_rows(), tmp_path)
    assert not stale.exists()
    assert len(list(tmp_path.glob("threshold-rows-*.csv"))) == len(m.CHECKPOINTS)


def test_no_staging_files_survive_a_successful_write(tmp_path: Path) -> None:
    m = _load()
    m.write_csvs(m.build_rows(), tmp_path)
    assert not list(tmp_path.glob("*.tmp"))


def test_written_files_use_lf_only_line_endings(tmp_path: Path) -> None:
    """Power Automate split on LF and got a bare CR as the last column's value.

    csv.writer defaults to lineterminator='\r\n'. `newline=""` stops the OS
    translating on top of that, which is why the file was not CRLF-doubled —
    but the csv module still wrote CR itself, and a parser that splits on LF
    leaves it on whichever column happens to be last. Here that was ParentId,
    a Lookup id, so SharePoint received "\r" and refused the item.
    """
    m = _load()
    written = m.write_csvs(m.build_rows(owner_id="11", parent_id="1"), tmp_path)
    for target in written:
        raw = target.read_bytes()
        assert bytes([13]) not in raw, f"{target.name} contains a CR byte"
    # And the value a LF-splitting parser sees for the LAST column is clean.
    lines = written[0].read_bytes().decode("utf-8").split("\n")
    assert lines[0].split(",")[-1] == "ParentId"
    assert lines[1].split(",")[-1] == ""


def test_no_field_carries_leading_or_trailing_whitespace(tmp_path: Path) -> None:
    """A stray space or CR in an id column is invisible in a spreadsheet and
    fatal to a batch create, which is non-transactional and so fails per item
    in silence."""
    m = _load()
    m.write_csvs(m.build_rows(owner_id="11", parent_id="1"), tmp_path)
    for row in _union(tmp_path):
        for column, value in row.items():
            assert value == value.strip(), f"{column}={value!r} has stray whitespace"
