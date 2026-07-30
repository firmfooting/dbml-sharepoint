# test/test_threshold_rows.py
"""The fixture's composition is the experiment's control.

Every number here is one the threshold probe's expectations are written
against. A row generator that silently changes a count turns "this query
returned fewer rows than expected" from a finding into a mystery.
"""

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
